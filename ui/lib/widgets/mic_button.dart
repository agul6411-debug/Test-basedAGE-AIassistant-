import 'package:flutter/material.dart';
import '../theme.dart';

class BigMicButton extends StatefulWidget {
  final String activeState; // idle, listening, thinking, speaking
  final VoidCallback onTap;

  const BigMicButton({
    super.key,
    required this.activeState,
    required this.onTap,
  });

  @override
  State<BigMicButton> createState() => _BigMicButtonState();
}

class _BigMicButtonState extends State<BigMicButton> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<double> _rippleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );

    _scaleAnimation = Tween<double>(begin: 1.0, end: 1.08).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );

    _rippleAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );

    if (widget.activeState != 'idle') {
      _controller.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(covariant BigMicButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.activeState != oldWidget.activeState) {
      if (widget.activeState == 'idle') {
        _controller.stop();
        _controller.reset();
      } else {
        _controller.repeat(reverse: true);
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    Color ringColor;
    Color iconColor;
    String statusLabel;
    IconData centerIcon;

    switch (widget.activeState) {
      case 'listening':
        ringColor = AgeTheme.amberAccent;
        iconColor = Colors.black;
        statusLabel = 'Listening...';
        centerIcon = Icons.mic;
        break;
      case 'thinking':
        ringColor = AgeTheme.amberAccent;
        iconColor = AgeTheme.amberAccent;
        statusLabel = 'Thinking...';
        centerIcon = Icons.psychology;
        break;
      case 'speaking':
        ringColor = AgeTheme.mintSuccess;
        iconColor = Colors.black;
        statusLabel = 'Speaking...';
        centerIcon = Icons.volume_up;
        break;
      case 'idle':
      default:
        ringColor = AgeTheme.borderDark;
        iconColor = AgeTheme.amberAccent;
        statusLabel = 'Tap or say "Hey AGE"';
        centerIcon = Icons.mic_none;
        break;
    }

    final isActionActive = widget.activeState != 'idle';

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        GestureDetector(
          onTap: widget.onTap,
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, child) {
              final scale = isActionActive ? _scaleAnimation.value : 1.0;
              final ripple = isActionActive ? _rippleAnimation.value : 0.0;

              return Stack(
                alignment: Alignment.center,
                children: [
                  // Animated Outer Glow / Ripple Ring
                  if (isActionActive)
                    Container(
                      width: 140 + (ripple * 40),
                      height: 140 + (ripple * 40),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: ringColor.withValues(alpha: (1.0 - ripple) * 0.25),
                      ),
                    ),

                  // Secondary Outer Glow Ring
                  Container(
                    width: 150 * scale,
                    height: 150 * scale,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: isActionActive ? ringColor.withValues(alpha: 0.5) : AgeTheme.borderDark,
                        width: 2,
                      ),
                      boxShadow: isActionActive
                          ? [
                              BoxShadow(
                                color: ringColor.withValues(alpha: 0.35),
                                blurRadius: 24,
                                spreadRadius: 4,
                              )
                            ]
                          : [],
                    ),
                  ),

                  // Core Mic Circle
                  Container(
                    width: 110,
                    height: 110,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: isActionActive
                          ? (widget.activeState == 'thinking' ? AgeTheme.darkCard : ringColor)
                          : AgeTheme.darkSurface,
                      border: Border.all(
                        color: ringColor,
                        width: 2,
                      ),
                    ),
                    child: Center(
                      child: widget.activeState == 'thinking'
                          ? SizedBox(
                              width: 48,
                              height: 48,
                              child: CircularProgressIndicator(
                                strokeWidth: 3,
                                valueColor: AlwaysStoppedAnimation<Color>(ringColor),
                              ),
                            )
                          : Icon(
                              centerIcon,
                              size: 48,
                              color: isActionActive
                                  ? (widget.activeState == 'thinking' ? ringColor : Colors.black)
                                  : iconColor,
                            ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),

        const SizedBox(height: 20),

        // Status Label
        Text(
          statusLabel,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: isActionActive ? ringColor : AgeTheme.textSecondary,
                fontWeight: FontWeight.w600,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          'Hotkey: Ctrl+Space',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AgeTheme.textMuted,
                fontSize: 12,
              ),
        ),
      ],
    );
  }
}
