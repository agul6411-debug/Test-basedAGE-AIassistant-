import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final TextEditingController _groqKeyCtrl = TextEditingController();
  bool _obscureKey = true;
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
  void dispose() {
    _groqKeyCtrl.dispose();
    super.dispose();
  }

  void _saveGroqKey(CoreClient client) {
    final key = _groqKeyCtrl.text.trim();
    if (key.isNotEmpty) {
      client.setGroqApiKey(key);
      setState(() => _savedFeedback = true);
      Future.delayed(const Duration(seconds: 2), () {
        if (mounted) setState(() => _savedFeedback = false);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Groq API Key saved successfully!'),
          backgroundColor: AgeTheme.mintSuccess,
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final settings = client.settings;
    final isGroqActive = client.isGroqConfigured;
    final currentModel = client.groqModel;

    final allowlist = (settings['app_allowlist'] as Map<String, dynamic>?) ?? {
      'notepad': 'notepad.exe',
      'calc': 'calc.exe',
      'chrome': 'chrome.exe',
      'edge': 'msedge.exe',
      'explorer': 'explorer.exe',
      'vscode': 'code.cmd',
    };

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Settings & AI Engine',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            'Configure Groq Cloud API, conversational memory, voice hotkeys, and inspect safe allowlists.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 24),

          // 1. Groq Cloud Engine Configuration Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AgeTheme.amberAccent.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.bolt, color: AgeTheme.amberAccent, size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Groq Cloud AI (High Performance / 0% PC Load)',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            Text(
                              'Offloads heavy LLM computing to Groq Cloud for instant conversation in Roman Urdu & English.',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      _Badge(
                        text: isGroqActive ? 'CONNECTED' : 'KEY REQUIRED',
                        color: isGroqActive ? AgeTheme.mintSuccess : AgeTheme.amberAccent,
                      ),
                    ],
                  ),
                  const Divider(color: AgeTheme.borderDark, height: 24),

                  // Groq API Key Input
                  const Text(
                    'API Key',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AgeTheme.textPrimary),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    decoration: BoxDecoration(
                      color: AgeTheme.darkSurface,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AgeTheme.borderDark),
                    ),
                    child: Row(
                      children: [
                        const SizedBox(width: 12),
                        const Icon(Icons.key, size: 18, color: AgeTheme.textMuted),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextField(
                            controller: _groqKeyCtrl,
                            obscureText: _obscureKey,
                            style: const TextStyle(fontSize: 13, color: AgeTheme.textPrimary, fontFamily: 'monospace'),
                            decoration: const InputDecoration(
                              hintText: 'Enter your Groq key (gsk_...)',
                              hintStyle: TextStyle(fontSize: 12, color: AgeTheme.textMuted),
                              border: InputBorder.none,
                            ),
                          ),
                        ),
                        IconButton(
                          icon: Icon(_obscureKey ? Icons.visibility_off : Icons.visibility, size: 18, color: AgeTheme.textMuted),
                          onPressed: () => setState(() => _obscureKey = !_obscureKey),
                        ),
                        IconButton(
                          icon: const Icon(Icons.content_paste, size: 18, color: AgeTheme.amberAccent),
                          tooltip: 'Paste',
                          onPressed: () async {
                            final clip = await Clipboard.getData('text/plain');
                            if (clip?.text != null) {
                              _groqKeyCtrl.text = clip!.text!.trim();
                            }
                          },
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 8),

                  Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'Get a free API key at console.groq.com/keys',
                          style: TextStyle(fontSize: 11, color: AgeTheme.mintSuccess),
                        ),
                      ),
                      ElevatedButton.icon(
                        onPressed: () => _saveGroqKey(client),
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

                  // Model Dropdown
                  const Text(
                    'Active Model',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AgeTheme.textPrimary),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                    decoration: BoxDecoration(
                      color: AgeTheme.darkSurface,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AgeTheme.borderDark),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: _availableModels.any((m) => m['id'] == currentModel) ? currentModel : 'qwen/qwen3.8-27b',
                        isExpanded: true,
                        dropdownColor: AgeTheme.darkSurface,
                        style: const TextStyle(color: AgeTheme.textPrimary, fontSize: 13),
                        items: _availableModels.map((m) {
                          return DropdownMenuItem<String>(
                            value: m['id'],
                            child: Row(
                              children: [
                                Text(m['label']!, style: const TextStyle(fontWeight: FontWeight.w600)),
                                const SizedBox(width: 8),
                                Text('• ${m['desc']!}', style: const TextStyle(color: AgeTheme.textMuted, fontSize: 11)),
                              ],
                            ),
                          );
                        }).toList(),
                        onChanged: (val) {
                          if (val != null) client.setGroqModel(val);
                        },
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Clear memory button
                  Row(
                    children: [
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Conversation Context Memory',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 12, color: AgeTheme.textPrimary),
                            ),
                            Text(
                              'Remembers preceding questions and conversation context.',
                              style: TextStyle(fontSize: 11, color: AgeTheme.textMuted),
                            ),
                          ],
                        ),
                      ),
                      OutlinedButton.icon(
                        onPressed: () {
                          client.clearMemory();
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Chat memory buffer cleared.'),
                              backgroundColor: AgeTheme.amberAccent,
                              duration: Duration(seconds: 2),
                            ),
                          );
                        },
                        icon: const Icon(Icons.delete_sweep, size: 16, color: AgeTheme.amberAccent),
                        label: const Text('Reset Memory', style: TextStyle(fontSize: 12, color: AgeTheme.amberAccent)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 2. Voice & Hotkey Settings
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Voice & Hotkey Triggers',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const Divider(color: AgeTheme.borderDark, height: 24),
                  _SettingRow(
                    title: 'Wake Word',
                    subtitle: 'Spoken wake trigger keyword',
                    valueWidget: _Badge(text: settings['wake_word']?.toString() ?? 'Hey AGE', color: AgeTheme.amberAccent),
                  ),
                  const SizedBox(height: 16),
                  _SettingRow(
                    title: 'Wake Word Backup Hotkey',
                    subtitle: 'Press anywhere in Windows to trigger listening immediately',
                    valueWidget: _Badge(text: settings['wake_word_hotkey']?.toString() ?? 'Ctrl+Space', color: AgeTheme.amberAccent),
                  ),
                  const SizedBox(height: 16),
                  _SettingRow(
                    title: 'Emergency Stop Hotkey',
                    subtitle: 'Instantly halts mic, camera, mouse, and running actions',
                    valueWidget: _Badge(text: settings['emergency_stop_hotkey']?.toString() ?? 'Ctrl+Shift+Esc', color: AgeTheme.dangerRed),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 3. Startup Option (Task Scheduler)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AgeTheme.mintSuccess.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.rocket_launch, color: AgeTheme.mintSuccess, size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Logon Autostart (Windows Task Scheduler)',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            Text(
                              'Security Rule 9: Runs at user logon strictly as the NORMAL user (no admin rights).',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const Divider(color: AgeTheme.borderDark, height: 24),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AgeTheme.darkSurface,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AgeTheme.borderDark),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.check_circle, size: 16, color: AgeTheme.mintSuccess),
                        SizedBox(width: 8),
                        Text(
                          'Task: "AGE_Assistant" (Created via schtasks without elevation)',
                          style: TextStyle(fontSize: 12, color: AgeTheme.textPrimary, fontFamily: 'monospace'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 4. Security Rule 4: Application Allowlist
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AgeTheme.amberAccent.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.shield, color: AgeTheme.amberAccent, size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Application Launch Allowlist',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            Text(
                              'Security Rule 4: Apps can ONLY be launched from this pre-approved list in config.yaml.',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const Divider(color: AgeTheme.borderDark, height: 24),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: allowlist.entries.map((e) {
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: AgeTheme.darkSurface,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AgeTheme.borderDark),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.apps, size: 14, color: AgeTheme.amberAccent),
                            const SizedBox(width: 8),
                            Text(
                              e.key,
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AgeTheme.textPrimary),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              '(${e.value})',
                              style: const TextStyle(fontSize: 11, color: AgeTheme.textMuted, fontFamily: 'monospace'),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget valueWidget;

  const _SettingRow({
    required this.title,
    required this.subtitle,
    required this.valueWidget,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AgeTheme.textPrimary)),
              const SizedBox(height: 2),
              Text(subtitle, style: const TextStyle(fontSize: 11, color: AgeTheme.textMuted)),
            ],
          ),
        ),
        valueWidget,
      ],
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color color;

  const _Badge({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: color, fontFamily: 'monospace'),
      ),
    );
  }
}
