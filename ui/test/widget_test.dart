import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:age_ui/core_client.dart';
import 'package:age_ui/main.dart';

void main() {
  testWidgets('AgeApp loads shell and shows header title', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => CoreClient(),
        child: const AgeApp(),
      ),
    );

    // Verify header title and navigation items
    expect(find.text('AGE'), findsOneWidget);
    expect(find.text('MY BEST FRIEND AI'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Controls'), findsOneWidget);
  });
}

