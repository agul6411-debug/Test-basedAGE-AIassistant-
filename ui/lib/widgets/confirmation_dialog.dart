import 'dart:async';
import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

class ConfirmationModal extends StatefulWidget {
  final ConfirmationPrompt prompt;
  final void Function(bool confirmed) onDecision;

  const ConfirmationModal({
    super.key,
    required this.prompt,
    required this.onDecision,
  });

  @override
  State<ConfirmationModal> createState() => _ConfirmationModalState();
}

class _ConfirmationModalState extends State<ConfirmationModal> {
  late int _remainingSec;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _remainingSec = widget.prompt.timeoutSec.toInt();
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (_remainingSec > 1) {
        setState(() => _remainingSec--);
      } else {
        t.cancel();
        widget.onDecision(false); // Default to safe Cancel on timeout
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AgeTheme.darkSurface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AgeTheme.amberAccent, width: 1.5),
      ),
      child: Container(
        width: 440,
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
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
                  child: const Icon(Icons.warning_amber_rounded, color: AgeTheme.amberAccent, size: 24),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Confirmation Required',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AgeTheme.textPrimary,
                            ),
                      ),
                      Text(
                        'Security Rule 5: Dangerous Action',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: AgeTheme.amberAccent,
                              fontSize: 11,
                            ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AgeTheme.darkCard,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AgeTheme.borderDark),
                  ),
                  child: Text(
                    '${_remainingSec}s',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AgeTheme.amberAccent),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 18),

            Text(
              widget.prompt.prompt,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: AgeTheme.textPrimary,
                    height: 1.4,
                  ),
            ),

            const SizedBox(height: 8),

            Text(
              'Target action: "${widget.prompt.actionName}"',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AgeTheme.textMuted,
                    fontStyle: FontStyle.italic,
                  ),
            ),

            const SizedBox(height: 24),

            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton(
                  onPressed: () => widget.onDecision(false),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 12),
                ElevatedButton(
                  onPressed: () => widget.onDecision(true),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AgeTheme.amberAccent,
                    foregroundColor: Colors.black,
                  ),
                  child: const Text('Confirm Action'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
