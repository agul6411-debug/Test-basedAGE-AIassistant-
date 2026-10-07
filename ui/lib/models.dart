class CommandLogItem {
  final String timestamp;
  final String action;
  final Map<String, dynamic> parameters;
  final String result;
  final bool success;

  CommandLogItem({
    required this.timestamp,
    required this.action,
    required this.parameters,
    required this.result,
    required this.success,
  });

  factory CommandLogItem.fromJson(Map<String, dynamic> json) {
    return CommandLogItem(
      timestamp: json['timestamp'] as String? ?? '',
      action: json['action'] as String? ?? 'command',
      parameters: json['parameters'] as Map<String, dynamic>? ?? {},
      result: json['result'] as String? ?? '',
      success: json['success'] as bool? ?? false,
    );
  }
}

class ConfirmationPrompt {
  final String actionName;
  final String prompt;
  final double timeoutSec;

  ConfirmationPrompt({
    required this.actionName,
    required this.prompt,
    this.timeoutSec = 10.0,
  });
}

class SystemStatus {
  final bool micActive;
  final bool cameraActive;
  final bool handMouseActive;
  final bool offlineMode;
  final bool coreRunning;
  final String activeState; // idle, listening, thinking, speaking
  final Map<String, String> models;
  final int layoutSnapshotsCount;
  final List<CommandLogItem> recentCommands;

  SystemStatus({
    this.micActive = false,
    this.cameraActive = false,
    this.handMouseActive = false,
    this.offlineMode = true,
    this.coreRunning = false,
    this.activeState = 'idle',
    this.models = const {},
    this.layoutSnapshotsCount = 0,
    this.recentCommands = const [],
  });

  factory SystemStatus.fromJson(Map<String, dynamic> json) {
    final rawRecent = json['recent_commands'] as List<dynamic>? ?? [];
    final recent = rawRecent
        .map((e) => CommandLogItem.fromJson(e as Map<String, dynamic>))
        .toList();

    final rawModels = json['models'] as Map<String, dynamic>? ?? {};
    final models = rawModels.map((k, v) => MapEntry(k, v.toString()));

    return SystemStatus(
      micActive: json['mic_active'] as bool? ?? false,
      cameraActive: json['camera_active'] as bool? ?? false,
      handMouseActive: json['hand_mouse_active'] as bool? ?? false,
      offlineMode: json['offline_mode'] as bool? ?? true,
      coreRunning: json['core_running'] as bool? ?? true,
      activeState: json['active_state'] as String? ?? 'idle',
      models: models,
      layoutSnapshotsCount: json['layout_snapshots_count'] as int? ?? 0,
      recentCommands: recent,
    );
  }
}
