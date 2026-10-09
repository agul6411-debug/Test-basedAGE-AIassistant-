import 'dart:io';
import 'package:flutter/foundation.dart';

Future<String?> readDiskToken() async {
  final candidates = [
    'data/sessions/session.token',
    '../data/sessions/session.token',
    '../../data/sessions/session.token',
  ];

  for (final p in candidates) {
    try {
      final f = File(p);
      if (await f.exists()) {
        final t = (await f.readAsString()).trim();
        if (t.isNotEmpty) return t;
      }
    } catch (_) {}
  }
  return null;
}

Future<void> maybeSpawnCore() async {
  try {
    final pythonCandidates = [
      '.venv/Scripts/python.exe',
      '../.venv/Scripts/python.exe',
      'python',
    ];

    String? pythonExe;
    String? workingDir;

    for (final py in pythonCandidates) {
      if (File(py).existsSync()) {
        pythonExe = py;
        workingDir = py.startsWith('..') ? '..' : '.';
        break;
      }
    }

    if (pythonExe != null) {
      debugPrint('Core server offline. Auto-starting AGE Core runner via $pythonExe...');
      await Process.start(
        pythonExe,
        ['-m', 'core.server.runner'],
        workingDirectory: workingDir,
        mode: ProcessStartMode.detached,
      );
      await Future.delayed(const Duration(milliseconds: 1500));
    }
  } catch (e) {
    debugPrint('Failed to auto-spawn core: $e');
  }
}
