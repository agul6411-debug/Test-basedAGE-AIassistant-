import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../theme.dart';

class AgeHeader extends StatelessWidget implements PreferredSizeWidget {
  const AgeHeader({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(64);

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final isConnected = client.connectionState == CoreConnectionState.connected;
    final status = client.status;

    return LayoutBuilder(
      builder: (context, constraints) {
        final isNarrow = constraints.maxWidth < 950;
        final isVeryNarrow = constraints.maxWidth < 750;

        return Container(
          height: 64,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: const BoxDecoration(
            color: AgeTheme.darkSurface,
            border: Border(
              bottom: BorderSide(color: AgeTheme.borderDark, width: 1),
            ),
          ),
          child: Row(
            children: [
              // App Logo & Title
              Row(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: AgeTheme.amberAccent.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                      border: Border.all(color: AgeTheme.amberAccent, width: 1.5),
                    ),
                    child: const Center(
                      child: Text(
                        'A',
                        style: TextStyle(
                          color: AgeTheme.amberAccent,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'AGE',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                      ),
                      if (!isVeryNarrow)
                        Text(
                          'MY BEST FRIEND AI',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                fontSize: 10,
                                letterSpacing: 1.0,
                              ),
                        ),
                    ],
                  ),
                ],
              ),

              const SizedBox(width: 16),

              // Connection status badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: isConnected ? AgeTheme.mintSuccess.withValues(alpha: 0.1) : AgeTheme.dangerRed.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isConnected ? AgeTheme.mintSuccess.withValues(alpha: 0.3) : AgeTheme.dangerRed.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: isConnected ? AgeTheme.mintSuccess : AgeTheme.dangerRed,
                        shape: BoxShape.circle,
                      ),
                    ),
                    if (!isVeryNarrow) ...[
                      const SizedBox(width: 6),
                      Text(
                        isConnected ? 'Core Connected' : (client.connectionState == CoreConnectionState.unauthorized ? 'Unauthorized Token' : 'Core Offline'),
                        style: TextStyle(
                          fontSize: 11,
                          color: isConnected ? AgeTheme.mintSuccess : AgeTheme.dangerRed,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ],
                ),
              ),

              const Spacer(),

              // Status Pills
              _StatusPill(
                icon: Icons.mic,
                label: 'Mic',
                isActive: status.micActive || client.activeState != 'idle',
                activeColor: AgeTheme.amberAccent,
                compact: isNarrow,
              ),
              const SizedBox(width: 6),
              _StatusPill(
                icon: Icons.videocam,
                label: 'Camera',
                isActive: status.cameraActive,
                activeColor: AgeTheme.mintSuccess,
                compact: isNarrow,
              ),
              const SizedBox(width: 6),
              _StatusPill(
                icon: Icons.security,
                label: '100% Offline',
                isActive: true,
                activeColor: AgeTheme.mintSuccess,
                compact: isNarrow,
              ),

              const SizedBox(width: 12),

              // ALWAYS VISIBLE EMERGENCY STOP BUTTON
              ElevatedButton.icon(
                onPressed: () {
                  client.emergencyStop();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('EMERGENCY STOP TRIGGERED: All hardware halted!'),
                      backgroundColor: AgeTheme.dangerRed,
                      duration: Duration(seconds: 3),
                    ),
                  );
                },
                icon: const Icon(Icons.stop_circle, color: Colors.white, size: 18),
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'STOP',
                      style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                    if (!isNarrow) ...[
                      const SizedBox(width: 6),
                      const Text(
                        'Ctrl+Shift+Esc',
                        style: TextStyle(color: Colors.white70, fontSize: 10),
                      ),
                    ],
                  ],
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AgeTheme.dangerRed,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  elevation: 4,
                  shadowColor: AgeTheme.dangerRed.withValues(alpha: 0.5),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StatusPill extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final Color activeColor;
  final bool compact;

  const _StatusPill({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.activeColor,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final fg = isActive ? activeColor : AgeTheme.textMuted;
    final bg = isActive ? activeColor.withValues(alpha: 0.12) : Colors.transparent;
    final border = isActive ? activeColor.withValues(alpha: 0.3) : AgeTheme.borderDark;

    return Tooltip(
      message: label,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 10, vertical: 5),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: border, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: fg),
            if (!compact) ...[
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: fg,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
