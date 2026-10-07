import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../theme.dart';
import '../widgets/mic_button.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _inputCtrl = TextEditingController();

  @override
  void dispose() {
    _inputCtrl.dispose();
    super.dispose();
  }

  void _submitCommand(CoreClient client) {
    final text = _inputCtrl.text.trim();
    if (text.isNotEmpty) {
      client.executeCommand(text);
      _inputCtrl.clear();
    }
  }

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final recent = client.status.recentCommands;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Left Panel: Big Mic & Command Input
          Expanded(
            flex: 3,
            child: LayoutBuilder(
              builder: (context, box) {
                return SingleChildScrollView(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: box.maxHeight),
                    child: IntrinsicHeight(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const SizedBox(height: 12),
                          BigMicButton(
                            activeState: client.activeState,
                            onTap: () => client.toggleListening(),
                          ),
                          const SizedBox(height: 20),

                          // Quick suggestions pills
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            alignment: WrapAlignment.center,
                            children: [
                              _QuickChip(label: 'open notepad', onTap: () => client.executeCommand('open notepad')),
                              _QuickChip(label: 'volume up', onTap: () => client.executeCommand('volume up')),
                              _QuickChip(label: 'save my desktop', onTap: () => client.executeCommand('save my desktop')),
                              _QuickChip(label: 'restore my desktop', onTap: () => client.executeCommand('restore my desktop')),
                              _QuickChip(label: 'lock the screen', onTap: () => client.executeCommand('lock the screen')),
                            ],
                          ),

                          const SizedBox(height: 16),

                          // Typed Command Bar
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                            decoration: BoxDecoration(
                              color: AgeTheme.darkCard,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: AgeTheme.borderDark),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.keyboard, color: AgeTheme.textMuted, size: 20),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: TextField(
                                    controller: _inputCtrl,
                                    onSubmitted: (_) => _submitCommand(client),
                                    style: const TextStyle(color: AgeTheme.textPrimary, fontSize: 14),
                                    decoration: const InputDecoration(
                                      hintText: 'Type an offline command (e.g. "open calc", "save my desktop")...',
                                      hintStyle: TextStyle(color: AgeTheme.textMuted, fontSize: 13),
                                      border: InputBorder.none,
                                    ),
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(Icons.arrow_upward, color: AgeTheme.amberAccent, size: 20),
                                  onPressed: () => _submitCommand(client),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),

          const SizedBox(width: 24),

          // Right Panel: Recent Commands Feed
          Expanded(
            flex: 2,
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.history, color: AgeTheme.amberAccent, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Recent Actions',
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: AgeTheme.textPrimary,
                                ),
                          ),
                        ),
                        Text(
                          '${recent.length} logged',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                    const Divider(color: AgeTheme.borderDark, height: 24),
                    Expanded(
                      child: recent.isEmpty
                          ? Center(
                              child: Text(
                                'No recent commands executed yet.\nSpeak or type a command to begin.',
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            )
                          : ListView.separated(
                              itemCount: recent.length,
                              separatorBuilder: (context, index) => const SizedBox(height: 8),
                              itemBuilder: (context, index) {
                                final item = recent[index];
                                return Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: AgeTheme.darkSurface,
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(
                                      color: item.success ? AgeTheme.mintSuccess.withValues(alpha: 0.2) : AgeTheme.dangerRed.withValues(alpha: 0.2),
                                    ),
                                  ),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Icon(
                                            item.success ? Icons.check_circle : Icons.error,
                                            size: 14,
                                            color: item.success ? AgeTheme.mintSuccess : AgeTheme.dangerRed,
                                          ),
                                          const SizedBox(width: 6),
                                          Text(
                                            item.action,
                                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                                          ),
                                          const Spacer(),
                                          Text(
                                            item.timestamp.split('T').last.split('.').first,
                                            style: const TextStyle(fontSize: 10, color: AgeTheme.textMuted),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        item.result,
                                        style: const TextStyle(fontSize: 11, color: AgeTheme.textSecondary),
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _QuickChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 11, color: AgeTheme.textSecondary)),
      backgroundColor: AgeTheme.darkCard,
      side: const BorderSide(color: AgeTheme.borderDark),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      onPressed: onTap,
    );
  }
}
