import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import 'models.dart';
import 'platform/token_helper.dart' as token_helper;

enum CoreConnectionState {
  disconnected,
  connecting,
  connected,
  unauthorized,
}

class CoreClient extends ChangeNotifier {
  static const String serverHost = '127.0.0.1';
  static const int serverPort = 8765;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  Timer? _statusPollTimer;

  CoreConnectionState _connectionState = CoreConnectionState.disconnected;
  String _activeState = 'idle'; // idle, listening, thinking, speaking
  SystemStatus _status = SystemStatus();
  ConfirmationPrompt? _activeConfirmation;
  final List<CommandLogItem> _conversationLog = [];
  Map<String, dynamic> _settings = {};

  CoreConnectionState get connectionState => _connectionState;
  String get activeState => _activeState;
  SystemStatus get status => _status;
  ConfirmationPrompt? get activeConfirmation => _activeConfirmation;
  List<CommandLogItem> get conversationLog => List.unmodifiable(_conversationLog);
  Map<String, dynamic> get settings => Map.unmodifiable(_settings);

  bool get isGroqConfigured {
    final groq = _settings['groq'];
    if (groq is Map) {
      return groq['configured'] == true || groq['has_key'] == true;
    }
    return false;
  }

  String get groqModel {
    final groq = _settings['groq'];
    if (groq is Map && groq['model'] != null) {
      return groq['model'].toString();
    }
    return 'qwen/qwen3.8-27b';
  }

  CoreClient() {
    connect();
  }

  /// Locate and read the session token from disk or HTTP endpoint.
  Future<String?> _readToken() async {
    if (kIsWeb) {
      // 1. Check query parameter first
      final queryToken = Uri.base.queryParameters['token'];
      if (queryToken != null && queryToken.trim().isNotEmpty) {
        return queryToken.trim();
      }

      // 2. Fetch from local loopback endpoint /api/token
      try {
        final host = Uri.base.host.isNotEmpty ? Uri.base.host : serverHost;
        final port = Uri.base.port > 0 ? Uri.base.port : serverPort;
        final tokenUri = Uri.parse('http://$host:$port/api/token');
        final response = await http.get(tokenUri);
        if (response.statusCode == 200) {
          final data = jsonDecode(response.body) as Map<String, dynamic>;
          final token = data['token'] as String?;
          if (token != null && token.isNotEmpty) {
            return token;
          }
        }
      } catch (e) {
        debugPrint('Failed to fetch web token via /api/token: $e');
      }
      return null;
    }

    return token_helper.readDiskToken();
  }

  /// Launch core Python runner if server is offline (desktop only).
  Future<void> _maybeSpawnCore() async {
    await token_helper.maybeSpawnCore();
  }

  /// Connect to WebSocket server with automatic token exchange.
  Future<void> connect() async {
    if (_connectionState == CoreConnectionState.connecting || _connectionState == CoreConnectionState.connected) {
      return;
    }

    _connectionState = CoreConnectionState.connecting;
    notifyListeners();

    final token = await _readToken();
    if (token == null) {
      debugPrint('No session token found. Attempting to start core to generate token...');
      await _maybeSpawnCore();
    }

    final freshToken = await _readToken();
    final host = kIsWeb && Uri.base.host.isNotEmpty ? Uri.base.host : serverHost;
    final port = kIsWeb && Uri.base.port > 0 ? Uri.base.port : serverPort;
    final uri = Uri.parse('ws://$host:$port');

    try {
      _channel = WebSocketChannel.connect(uri);
      await _channel!.ready;

      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );

      // Send initial authentication handshake
      if (freshToken != null) {
        _channel!.sink.add(jsonEncode({
          'type': 'auth',
          'token': freshToken,
        }));
      }
    } catch (e) {
      debugPrint('WebSocket connection attempt failed: $e');
      await _maybeSpawnCore();
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final data = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = data['type'] as String?;

      switch (type) {
        case 'auth_result':
          final success = data['success'] as bool? ?? false;
          if (success) {
            _connectionState = CoreConnectionState.connected;
            _reconnectTimer?.cancel();
            _startStatusPolling();
            querySettings();
            _send({'type': 'start_listening'});
          } else {
            _connectionState = CoreConnectionState.unauthorized;
          }
          notifyListeners();
          break;

        case 'state_change':
          _activeState = data['state'] as String? ?? 'idle';
          notifyListeners();
          break;

        case 'status_update':
          _status = SystemStatus.fromJson(data);
          _activeState = _status.activeState;
          notifyListeners();
          break;

        case 'settings':
          _settings = data;
          notifyListeners();
          break;

        case 'command_result':
          final item = CommandLogItem(
            timestamp: data['timestamp'] as String? ?? DateTime.now().toIso8601String(),
            action: data['tool_name'] as String? ?? 'command',
            parameters: data['data'] as Map<String, dynamic>? ?? {},
            result: data['message'] as String? ?? '',
            success: data['success'] as bool? ?? false,
          );
          _conversationLog.insert(0, item);
          if (data['data'] != null && data['data']['requires_confirmation'] == true) {
            _activeConfirmation = ConfirmationPrompt(
              actionName: data['data']['action_name'] as String? ?? 'action',
              prompt: data['message'] as String? ?? 'Please confirm action.',
            );
          }
          notifyListeners();
          break;

        case 'confirmation_required':
          _activeConfirmation = ConfirmationPrompt(
            actionName: data['action_name'] as String? ?? 'action',
            prompt: data['prompt'] as String? ?? 'Confirmation required.',
            timeoutSec: (data['timeout_sec'] as num?)?.toDouble() ?? 10.0,
          );
          notifyListeners();
          break;

        case 'emergency_stop_triggered':
          _activeState = 'idle';
          _activeConfirmation = null;
          final item = CommandLogItem(
            timestamp: data['timestamp'] as String? ?? DateTime.now().toIso8601String(),
            action: 'emergency_stop',
            parameters: {},
            result: data['message'] as String? ?? 'Emergency stop executed.',
            success: true,
          );
          _conversationLog.insert(0, item);
          notifyListeners();
          break;

        case 'error':
          debugPrint('Server error event: ${data['message']}');
          break;
      }
    } catch (e) {
      debugPrint('Error parsing message: $e');
    }
  }

  void _onError(dynamic error) {
    debugPrint('WebSocket stream error: $error');
    _onDone();
  }

  void _onDone() {
    _channel = null;
    _subscription?.cancel();
    _subscription = null;
    _statusPollTimer?.cancel();
    if (_connectionState != CoreConnectionState.unauthorized) {
      _connectionState = CoreConnectionState.disconnected;
    }
    _activeState = 'idle';
    notifyListeners();
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      if (_connectionState != CoreConnectionState.connected) {
        connect();
      }
    });
  }

  void _startStatusPolling() {
    _statusPollTimer?.cancel();
    _statusPollTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      queryStatus();
    });
  }

  void _send(Map<String, dynamic> payload) {
    if (_connectionState == CoreConnectionState.connected && _channel != null) {
      _channel!.sink.add(jsonEncode(payload));
    }
  }

  // --- Client Actions ---

  void executeCommand(String text, {bool forceConfirmed = false}) {
    if (text.trim().isEmpty) return;
    _send({
      'type': 'execute_command',
      'text': text.trim(),
      'force_confirmed': forceConfirmed,
    });
  }

  void confirmAction(String actionName, bool confirmed) {
    _send({
      'type': 'confirm_action',
      'action_name': actionName,
      'confirmed': confirmed,
    });
    _activeConfirmation = null;
    notifyListeners();
  }

  void emergencyStop() {
    _send({'type': 'emergency_stop'});
  }

  void toggleHandMouse(bool enabled) {
    _send({'type': 'toggle_hand_mouse', 'enabled': enabled});
  }

  void saveLayout() {
    _send({'type': 'save_layout'});
  }

  void restoreLayout() {
    _send({'type': 'restore_layout'});
  }

  void queryStatus() {
    _send({'type': 'get_status'});
  }

  void querySettings() {
    _send({'type': 'get_settings'});
  }

  void toggleListening() {
    if (_activeState != 'idle') {
      _send({'type': 'stop_listening'});
    } else {
      _send({'type': 'start_listening'});
    }
  }

  void updateSetting(String key, dynamic value) {
    _send({
      'type': 'update_setting',
      'key': key,
      'value': value,
    });
  }

  void setGroqApiKey(String apiKey) {
    updateSetting('groq_api_key', apiKey.trim());
  }

  void setGroqModel(String model) {
    updateSetting('groq_model', model.trim());
  }

  void clearMemory() {
    updateSetting('clear_history', true);
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _statusPollTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}
