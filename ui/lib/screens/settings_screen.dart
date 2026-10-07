import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../theme.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final settings = client.settings;
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
            'Settings & Security Policy',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            'Configure wake word, global hotkeys, logon autostart, and inspect application allowlists.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 24),

          // 1. Voice & Hotkey Settings
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

          // 2. Startup Option (Task Scheduler)
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

          // 3. Security Rule 4: Application Allowlist
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
