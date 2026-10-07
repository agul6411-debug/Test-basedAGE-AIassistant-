import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../theme.dart';

class ControlsScreen extends StatefulWidget {
  const ControlsScreen({super.key});

  @override
  State<ControlsScreen> createState() => _ControlsScreenState();
}

class _ControlsScreenState extends State<ControlsScreen> {
  double _sensitivity = 1.2;
  double _deadZone = 6.0;

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final status = client.status;
    final isHandMouseActive = status.handMouseActive;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Hardware & Feature Controls',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            'Manage the hand-gesture webcam mouse, desktop layout snapshots, and local AI engines.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 24),

          // 1. Hand Mouse Card
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
                        child: const Icon(Icons.back_hand, color: AgeTheme.amberAccent, size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Hand-Gesture Mouse (MediaPipe + OpenCV)',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            Text(
                              'Control your mouse via 640x480 webcam in memory. Pinch = click, two fingers = scroll.',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      Switch(
                        value: isHandMouseActive,
                        activeThumbColor: AgeTheme.amberAccent,
                        onChanged: (val) {
                          client.toggleHandMouse(val);
                        },
                      ),
                    ],
                  ),

                  const Divider(color: AgeTheme.borderDark, height: 28),

                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text('Pointer Sensitivity', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500)),
                                Text('${_sensitivity.toStringAsFixed(1)}x', style: const TextStyle(fontSize: 12, color: AgeTheme.amberAccent)),
                              ],
                            ),
                            Slider(
                              value: _sensitivity,
                              min: 0.5,
                              max: 2.5,
                              divisions: 20,
                              activeColor: AgeTheme.amberAccent,
                              inactiveColor: AgeTheme.borderDark,
                              onChanged: (v) => setState(() => _sensitivity = v),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 24),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text('Dead Zone Threshold', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500)),
                                Text('${_deadZone.toStringAsFixed(0)} px', style: const TextStyle(fontSize: 12, color: AgeTheme.amberAccent)),
                              ],
                            ),
                            Slider(
                              value: _deadZone,
                              min: 2.0,
                              max: 15.0,
                              divisions: 13,
                              activeColor: AgeTheme.amberAccent,
                              inactiveColor: AgeTheme.borderDark,
                              onChanged: (v) => setState(() => _deadZone = v),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),

                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AgeTheme.darkSurface,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AgeTheme.borderDark),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.info_outline, size: 14, color: AgeTheme.textMuted),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Safety features active: 10-second hand absence auto-stop, One Euro jitter filter, frames processed in memory only.',
                            style: TextStyle(fontSize: 11, color: AgeTheme.textMuted),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 2. Desktop Layout Card
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
                        child: const Icon(Icons.dashboard_customize, color: AgeTheme.mintSuccess, size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Desktop Layout Manager',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            Text(
                              'Saves window sizes, coordinates, min/max states, and desktop icon positions to SQLite.',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AgeTheme.darkSurface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AgeTheme.borderDark),
                        ),
                        child: Text(
                          '${status.layoutSnapshotsCount} / 10 Snapshots',
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: AgeTheme.textSecondary),
                        ),
                      ),
                    ],
                  ),

                  const Divider(color: AgeTheme.borderDark, height: 28),

                  Row(
                    children: [
                      ElevatedButton.icon(
                        onPressed: () {
                          client.saveLayout();
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Desktop layout snapshot saved successfully.')),
                          );
                        },
                        icon: const Icon(Icons.save, size: 16),
                        label: const Text('Save My Desktop'),
                      ),
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: () {
                          client.restoreLayout();
                        },
                        icon: const Icon(Icons.restore, size: 16, color: AgeTheme.amberAccent),
                        label: const Text('Restore My Desktop'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 3. Local Models Status
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Offline Engine Status',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Zero telemetry. All speech models and Ollama run 100% locally on your laptop.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const Divider(color: AgeTheme.borderDark, height: 24),
                  Row(
                    children: [
                      _EngineCard(
                        name: 'Ollama LLM Fallback',
                        model: status.models['brain'] ?? 'qwen2.5:3b',
                        status: 'Ready (Localhost)',
                        statusColor: AgeTheme.mintSuccess,
                        icon: Icons.psychology,
                      ),
                      const SizedBox(width: 12),
                      _EngineCard(
                        name: 'Whisper STT',
                        model: status.models['stt'] ?? 'base.en',
                        status: 'Loaded (faster-whisper)',
                        statusColor: AgeTheme.mintSuccess,
                        icon: Icons.record_voice_over,
                      ),
                      const SizedBox(width: 12),
                      _EngineCard(
                        name: 'Piper TTS',
                        model: status.models['tts'] ?? 'Piper English',
                        status: 'Loaded in Memory',
                        statusColor: AgeTheme.mintSuccess,
                        icon: Icons.volume_up,
                      ),
                    ],
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

class _EngineCard extends StatelessWidget {
  final String name;
  final String model;
  final String status;
  final Color statusColor;
  final IconData icon;

  const _EngineCard({
    required this.name,
    required this.model,
    required this.status,
    required this.statusColor,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AgeTheme.darkSurface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AgeTheme.borderDark),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 16, color: AgeTheme.amberAccent),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    name,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(model, style: const TextStyle(fontSize: 13, color: AgeTheme.textPrimary)),
            const SizedBox(height: 4),
            Row(
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Text(status, style: TextStyle(fontSize: 11, color: statusColor)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
