import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme.dart';

/// Futuristic Neural Voice Orb that dynamically pulsates, ripples, and animates
/// based on the AI Companion's active state: idle, listening, thinking, speaking.
class VoiceOrb extends StatefulWidget {
  final String activeState; // idle, listening, thinking, speaking
  final VoidCallback onTap;
  final double size;

  const VoiceOrb({
    super.key,
    required this.activeState,
    required this.onTap,
    this.size = 220.0,
  });

  @override
  State<VoiceOrb> createState() => _VoiceOrbState();
}

class _VoiceOrbState extends State<VoiceOrb> with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _rotationController;
  late AnimationController _waveController;

  bool _isHovered = false;

  @override
  void initState() {
    super.initState();

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    )..repeat(reverse: true);

    _rotationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 12),
    )..repeat();

    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat();
  }

  @override
  void didUpdateWidget(covariant VoiceOrb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.activeState != oldWidget.activeState) {
      switch (widget.activeState) {
        case 'listening':
          _pulseController.duration = const Duration(milliseconds: 1100);
          _pulseController.repeat(reverse: true);
          _waveController.duration = const Duration(milliseconds: 900);
          _waveController.repeat();
          break;
        case 'thinking':
          _pulseController.duration = const Duration(milliseconds: 1400);
          _pulseController.repeat(reverse: true);
          _rotationController.duration = const Duration(seconds: 4);
          _rotationController.repeat();
          break;
        case 'speaking':
          _pulseController.duration = const Duration(milliseconds: 1000);
          _pulseController.repeat(reverse: true);
          _waveController.duration = const Duration(milliseconds: 1100);
          _waveController.repeat();
          break;
        case 'idle':
        default:
          _pulseController.duration = const Duration(milliseconds: 2600);
          _pulseController.repeat(reverse: true);
          _rotationController.duration = const Duration(seconds: 16);
          _rotationController.repeat();
          break;
      }
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _rotationController.dispose();
    _waveController.dispose();
    super.dispose();
  }

  (List<Color> palette, String label, String hint, IconData icon) _getStateTheme() {
    switch (widget.activeState) {
      case 'listening':
        return (
          [
            const Color(0xFFFFB547), // Amber
            const Color(0xFFFF7E1D), // Orange
            const Color(0xFFFFE082), // Soft gold
          ],
          'Listening to you...',
          'Speak freely in Urdu or English',
          Icons.mic,
        );
      case 'thinking':
        return (
          [
            const Color(0xFF8B5CF6), // Purple
            const Color(0xFF06B6D4), // Cyan
            const Color(0xFF3B82F6), // Blue
          ],
          'Thinking with Groq...',
          'Synthesizing fast response (<0.5s)',
          Icons.psychology,
        );
      case 'speaking':
        return (
          [
            const Color(0xFF5EEAD4), // Mint
            const Color(0xFF10B981), // Emerald
            const Color(0xFF22D3EE), // Cyan
          ],
          'Speaking...',
          'AGE is responding to you',
          Icons.volume_up,
        );
      case 'idle':
      default:
        return (
          [
            const Color(0xFF38BDF8), // Sky Blue
            const Color(0xFF818CF8), // Indigo
            const Color(0xFFFFB547), // Subtle Amber
          ],
          'Ready to Chat',
          'Tap orb or say "Hey AGE"',
          Icons.mic_none,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final themeData = _getStateTheme();
    final palette = themeData.$1;
    final statusLabel = themeData.$2;
    final hintText = themeData.$3;
    final centerIcon = themeData.$4;

    final isActive = widget.activeState != 'idle';

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        MouseRegion(
          cursor: SystemMouseCursors.click,
          onEnter: (_) => setState(() => _isHovered = true),
          onExit: (_) => setState(() => _isHovered = false),
          child: GestureDetector(
            onTap: widget.onTap,
            child: AnimatedBuilder(
              animation: Listenable.merge([
                _pulseController,
                _rotationController,
                _waveController,
              ]),
              builder: (context, child) {
                final pulse = _pulseController.value;
                final rotation = _rotationController.value * 2 * math.pi;
                final wave = _waveController.value;
                final hoverScale = _isHovered ? 1.05 : 1.0;

                return Transform.scale(
                  scale: hoverScale,
                  child: SizedBox(
                    width: widget.size,
                    height: widget.size,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        // Custom Painted Glowing Neural Waves & Rings
                        CustomPaint(
                          size: Size(widget.size, widget.size),
                          painter: _OrbPainter(
                            palette: palette,
                            pulse: pulse,
                            rotation: rotation,
                            wave: wave,
                            isActive: isActive,
                            activeState: widget.activeState,
                          ),
                        ),

                        // Core Glowing Glass Sphere
                        Container(
                          width: widget.size * 0.48,
                          height: widget.size * 0.48,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              center: const Alignment(-0.25, -0.3),
                              radius: 0.9,
                              colors: [
                                Colors.white.withValues(alpha: 0.25),
                                palette[0].withValues(alpha: 0.8),
                                palette[1],
                                const Color(0xFF0F172A),
                              ],
                              stops: const [0.0, 0.35, 0.7, 1.0],
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: palette[0].withValues(alpha: isActive ? 0.6 : 0.3),
                                blurRadius: isActive ? 36 : 22,
                                spreadRadius: isActive ? 6 : 2,
                              ),
                              BoxShadow(
                                color: palette[1].withValues(alpha: 0.4),
                                blurRadius: 48,
                                spreadRadius: 4,
                              ),
                            ],
                            border: Border.all(
                              color: Colors.white.withValues(alpha: 0.4),
                              width: 1.5,
                            ),
                          ),
                          child: Center(
                            child: Icon(
                              centerIcon,
                              color: Colors.white,
                              size: widget.size * 0.2,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ),

        const SizedBox(height: 14),

        // Glowing State Badge
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          decoration: BoxDecoration(
            color: palette[0].withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: palette[0].withValues(alpha: isActive ? 0.6 : 0.3),
              width: 1.2,
            ),
            boxShadow: isActive
                ? [
                    BoxShadow(
                      color: palette[0].withValues(alpha: 0.25),
                      blurRadius: 16,
                      spreadRadius: 1,
                    )
                  ]
                : [],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: palette[0],
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: palette[0],
                      blurRadius: 8,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                statusLabel,
                style: TextStyle(
                  color: palette[0],
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.3,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 6),

        // Dynamic Subtitle Hint
        Text(
          hintText,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: AgeTheme.textMuted,
            fontSize: 12,
            letterSpacing: 0.2,
          ),
        ),
      ],
    );
  }
}

class _OrbPainter extends CustomPainter {
  final List<Color> palette;
  final double pulse;
  final double rotation;
  final double wave;
  final bool isActive;
  final String activeState;

  _OrbPainter({
    required this.palette,
    required this.pulse,
    required this.rotation,
    required this.wave,
    required this.isActive,
    required this.activeState,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;

    // Outer Ambient Glow
    final ambientPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          palette[0].withValues(alpha: isActive ? 0.22 : 0.1),
          palette[1].withValues(alpha: isActive ? 0.12 : 0.04),
          Colors.transparent,
        ],
        stops: const [0.3, 0.7, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: radius));

    canvas.drawCircle(center, radius, ambientPaint);

    // Dynamic Concentric Glowing Rings
    final ringCount = isActive ? 3 : 2;
    for (int i = 0; i < ringCount; i++) {
      final ringProgress = (wave + (i * 0.33)) % 1.0;
      final currentRadius = (radius * 0.45) + (ringProgress * radius * 0.48);
      final alpha = (1.0 - ringProgress).clamp(0.0, 1.0) * (isActive ? 0.45 : 0.2);

      final ringPaint = Paint()
        ..color = palette[i % palette.length].withValues(alpha: alpha)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5;

      canvas.drawCircle(center, currentRadius, ringPaint);
    }

    // Orbital Arcs (Spinning Aura)
    final arcPaint = Paint()
      ..color = palette[0].withValues(alpha: isActive ? 0.55 : 0.25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round;

    final arcRadius = radius * 0.68 + (pulse * 6.0);
    final arcRect = Rect.fromCircle(center: center, radius: arcRadius);

    // Draw multi-orbital arcs with rotation
    canvas.drawArc(arcRect, rotation, 1.2, false, arcPaint);
    canvas.drawArc(arcRect, rotation + math.pi, 1.2, false, arcPaint);

    if (isActive) {
      final secondArcPaint = Paint()
        ..color = palette[1].withValues(alpha: 0.6)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round;

      final secondRect = Rect.fromCircle(center: center, radius: arcRadius + 12.0);
      canvas.drawArc(secondRect, -rotation * 1.4, 0.9, false, secondArcPaint);
      canvas.drawArc(secondRect, -rotation * 1.4 + math.pi, 0.9, false, secondArcPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _OrbPainter oldDelegate) {
    return oldDelegate.pulse != pulse ||
        oldDelegate.rotation != rotation ||
        oldDelegate.wave != wave ||
        oldDelegate.activeState != activeState;
  }
}
