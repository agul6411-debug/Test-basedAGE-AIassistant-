import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../core_client.dart';
import '../theme.dart';

class GroqSettingsDialog extends StatefulWidget {
  const GroqSettingsDialog({super.key});

  static Future<void> show(BuildContext context) {
    return showDialog<void>(
      context: context,
      barrierDismissible: true,
      builder: (context) => const GroqSettingsDialog(),
    );
  }

  @override
  State<GroqSettingsDialog> createState() => _GroqSettingsDialogState();
}

class _GroqSettingsDialogState extends State<GroqSettingsDialog> {
  final TextEditingController _keyCtrl = TextEditingController();
  bool _obscureKey = true;
  String _selectedModel = 'qwen/qwen3.8-27b';
  bool _savedFeedback = false;

  final List<Map<String, String>> _availableModels = [
    {
      'id': 'qwen/qwen3.8-27b',
      'label': 'Qwen 3.8 27B (Recommended)',
      'desc': 'Smartest, best Roman Urdu & general knowledge',
    },
    {
      'id': 'openai/gpt-oss-120b',
      'label': 'GPT OSS 120B (High Reasoning)',
      'desc': 'Deep reasoning and complex instructions',
    },
    {
      'id': 'openai/gpt-oss-20b',
      'label': 'GPT OSS 20B (Ultra-fast)',
      'desc': 'Fastest response time (<200ms)',
    },
  ];

  @override
  void initState() {
    super.initState();
    final client = context.read<CoreClient>();
    _selectedModel = client.groqModel;
  }

  @override
  void dispose() {
    _keyCtrl.dispose();
    super.dispose();
  }

  void _saveKey(CoreClient client) {
    final key = _keyCtrl.text.trim();
    if (key.isNotEmpty) {
      client.setGroqApiKey(key);
      setState(() => _savedFeedback = true);
      Future.delayed(const Duration(seconds: 2), () {
        if (mounted) setState(() => _savedFeedback = false);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Groq API Key saved successfully! Cloud AI is active.'),
          backgroundColor: AgeTheme.mintSuccess,
          duration: Duration(seconds: 3),
        ),
      );
    }
  }

  void _changeModel(CoreClient client, String newModel) {
    setState(() => _selectedModel = newModel);
    client.setGroqModel(newModel);
  }

  void _clearChatMemory(CoreClient client) {
    client.clearMemory();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Conversation memory buffer cleared.'),
        backgroundColor: AgeTheme.amberAccent,
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final isGroqActive = client.isGroqConfigured;

    return Dialog(
      backgroundColor: AgeTheme.darkSurface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AgeTheme.borderDark, width: 1),
      ),
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 580, maxHeight: 720),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Dialog Header
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AgeTheme.amberAccent.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.bolt, color: AgeTheme.amberAccent, size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Groq Cloud AI Settings',
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AgeTheme.textPrimary,
                              ),
                        ),
                        Text(
                          'Lightning-fast conversational intelligence (0% Laptop Load)',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: AgeTheme.textMuted,
                              ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AgeTheme.textMuted),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),

              const Divider(color: AgeTheme.borderDark, height: 28),

              Flexible(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Status Card
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: isGroqActive
                              ? AgeTheme.mintSuccess.withValues(alpha: 0.1)
                              : AgeTheme.amberAccent.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isGroqActive
                                ? AgeTheme.mintSuccess.withValues(alpha: 0.3)
                                : AgeTheme.amberAccent.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              isGroqActive ? Icons.check_circle : Icons.info_outline,
                              color: isGroqActive ? AgeTheme.mintSuccess : AgeTheme.amberAccent,
                              size: 22,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    isGroqActive ? 'Groq Cloud Active' : 'Groq API Key Required',
                                    style: TextStyle(
                                      color: isGroqActive ? AgeTheme.mintSuccess : AgeTheme.amberAccent,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 13,
                                    ),
                                  ),
                                  Text(
                                    isGroqActive
                                        ? 'Active Model: $_selectedModel. Responses take ~300ms with zero CPU/RAM strain.'
                                        : 'Paste your free Groq API key below to unlock conversational AI in Roman Urdu & English.',
                                    style: const TextStyle(fontSize: 11, color: AgeTheme.textSecondary),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 20),

                      // API Key Section
                      const Text(
                        'Groq API Key',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AgeTheme.textPrimary),
                      ),
                      const SizedBox(height: 6),
                      Container(
                        decoration: BoxDecoration(
                          color: AgeTheme.darkCard,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AgeTheme.borderDark),
                        ),
                        child: Row(
                          children: [
                            const SizedBox(width: 12),
                            const Icon(Icons.key, color: AgeTheme.textMuted, size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: TextField(
                                controller: _keyCtrl,
                                obscureText: _obscureKey,
                                style: const TextStyle(fontSize: 13, color: AgeTheme.textPrimary, fontFamily: 'monospace'),
                                decoration: const InputDecoration(
                                  hintText: 'Paste gsk_... key here',
                                  hintStyle: TextStyle(color: AgeTheme.textMuted, fontSize: 12),
                                  border: InputBorder.none,
                                ),
                              ),
                            ),
                            IconButton(
                              icon: Icon(_obscureKey ? Icons.visibility_off : Icons.visibility, size: 18, color: AgeTheme.textMuted),
                              onPressed: () => setState(() => _obscureKey = !_obscureKey),
                              tooltip: _obscureKey ? 'Show Key' : 'Hide Key',
                            ),
                            IconButton(
                              icon: const Icon(Icons.content_paste, size: 18, color: AgeTheme.amberAccent),
                              tooltip: 'Paste from clipboard',
                              onPressed: () async {
                                final clip = await Clipboard.getData('text/plain');
                                if (clip?.text != null) {
                                  _keyCtrl.text = clip!.text!.trim();
                                }
                              },
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 8),

                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Free API keys: console.groq.com/keys',
                              style: TextStyle(color: AgeTheme.mintSuccess.withValues(alpha: 0.9), fontSize: 11),
                            ),
                          ),
                          ElevatedButton.icon(
                            onPressed: () => _saveKey(client),
                            icon: Icon(_savedFeedback ? Icons.check : Icons.save, size: 16),
                            label: Text(_savedFeedback ? 'Saved!' : 'Save Key'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _savedFeedback ? AgeTheme.mintSuccess : AgeTheme.amberAccent,
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 20),

                      // Model Selection Section
                      const Text(
                        'AI Model',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AgeTheme.textPrimary),
                      ),
                      const SizedBox(height: 6),
                      Column(
                        children: _availableModels.map((m) {
                          final isSelected = _selectedModel == m['id'];
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: InkWell(
                              onTap: () => _changeModel(client, m['id']!),
                              borderRadius: BorderRadius.circular(10),
                              child: Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: isSelected ? AgeTheme.amberAccent.withValues(alpha: 0.12) : AgeTheme.darkCard,
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(
                                    color: isSelected ? AgeTheme.amberAccent : AgeTheme.borderDark,
                                    width: isSelected ? 1.5 : 1,
                                  ),
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      isSelected ? Icons.radio_button_checked : Icons.radio_button_off,
                                      color: isSelected ? AgeTheme.amberAccent : AgeTheme.textMuted,
                                      size: 18,
                                    ),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            m['label']!,
                                            style: TextStyle(
                                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                              color: isSelected ? AgeTheme.textPrimary : AgeTheme.textSecondary,
                                              fontSize: 13,
                                            ),
                                          ),
                                          Text(
                                            m['desc']!,
                                            style: const TextStyle(fontSize: 11, color: AgeTheme.textMuted),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          );
                        }).toList(),
                      ),

                      const SizedBox(height: 16),

                      // Reset Memory Buffer Section
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AgeTheme.darkCard,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AgeTheme.borderDark),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.psychology_alt, color: AgeTheme.textMuted, size: 20),
                            const SizedBox(width: 10),
                            const Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Multi-Turn Chat Memory',
                                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AgeTheme.textPrimary),
                                  ),
                                  Text(
                                    'Retains last 10 conversation turns for context.',
                                    style: TextStyle(fontSize: 11, color: AgeTheme.textMuted),
                                  ),
                                ],
                              ),
                            ),
                            OutlinedButton.icon(
                              onPressed: () => _clearChatMemory(client),
                              icon: const Icon(Icons.delete_sweep, size: 16, color: AgeTheme.amberAccent),
                              label: const Text('Reset', style: TextStyle(fontSize: 12, color: AgeTheme.amberAccent)),
                              style: OutlinedButton.styleFrom(
                                side: const BorderSide(color: AgeTheme.borderDark),
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Bottom Close Button
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Done', style: TextStyle(color: AgeTheme.amberAccent, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
