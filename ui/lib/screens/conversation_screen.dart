import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../models.dart';
import '../theme.dart';

class ConversationScreen extends StatefulWidget {
  const ConversationScreen({super.key});

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen> {
  String _filter = 'all'; // all, success, error

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final allLogs = client.conversationLog;

    final filtered = allLogs.where((item) {
      if (_filter == 'success') return item.success;
      if (_filter == 'error') return !item.success;
      return true;
    }).toList();

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Conversation & Action Log',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Security Rule 12: Actions logged with sensitive text masked automatically.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
              const Spacer(),

              // Filter Segmented Buttons
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'all', label: Text('All')),
                  ButtonSegment(value: 'success', label: Text('Success')),
                  ButtonSegment(value: 'error', label: Text('Errors')),
                ],
                selected: {_filter},
                onSelectionChanged: (val) {
                  setState(() => _filter = val.first);
                },
                style: const ButtonStyle(
                  visualDensity: VisualDensity.compact,
                ),
              ),
            ],
          ),

          const SizedBox(height: 20),

          Expanded(
            child: filtered.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.chat_bubble_outline, size: 48, color: AgeTheme.textMuted),
                        const SizedBox(height: 12),
                        Text(
                          'No conversation entries recorded yet.',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AgeTheme.textMuted),
                        ),
                      ],
                    ),
                  )
                : ListView.separated(
                    itemCount: filtered.length,
                    separatorBuilder: (context, index) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final item = filtered[index];
                      return _LogCard(item: item);
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _LogCard extends StatelessWidget {
  final CommandLogItem item;

  const _LogCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final statusColor = item.success ? AgeTheme.mintSuccess : AgeTheme.dangerRed;
    final statusBg = statusColor.withValues(alpha: 0.1);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: statusBg,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: statusColor.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        item.success ? Icons.check_circle_outline : Icons.cancel_outlined,
                        size: 13,
                        color: statusColor,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        item.action.toUpperCase(),
                        style: TextStyle(
                          color: statusColor,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  item.timestamp.split('T').last.split('.').first,
                  style: const TextStyle(fontSize: 11, color: AgeTheme.textMuted),
                ),
                const Spacer(),
                Text(
                  item.success ? 'COMPLETED' : 'REJECTED / FAILED',
                  style: TextStyle(fontSize: 10, color: statusColor, fontWeight: FontWeight.bold),
                ),
              ],
            ),

            const SizedBox(height: 10),

            Text(
              item.result,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AgeTheme.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
            ),

            if (item.parameters.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AgeTheme.darkSurface,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AgeTheme.borderDark),
                ),
                child: Text(
                  'Parameters: ${item.parameters}',
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 11,
                    color: AgeTheme.textMuted,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
