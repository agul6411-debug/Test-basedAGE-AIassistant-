import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'core_client.dart';
import 'screens/controls_screen.dart';
import 'screens/conversation_screen.dart';
import 'screens/home_screen.dart';
import 'screens/settings_screen.dart';
import 'theme.dart';
import 'widgets/confirmation_dialog.dart';
import 'widgets/header.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Security Rule 7: Strictly disable outbound runtime network calls for fonts
  GoogleFonts.config.allowRuntimeFetching = false;
  runApp(
    ChangeNotifierProvider(
      create: (_) => CoreClient(),
      child: const AgeApp(),
    ),
  );
}

class AgeApp extends StatelessWidget {
  const AgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AGE - MY BEST FRIEND AI',
      debugShowCheckedModeBanner: false,
      theme: AgeTheme.darkTheme,
      home: const MainShell(),
    );
  }
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _selectedIndex = 0;
  bool _dialogShowing = false;

  final List<Widget> _screens = const [
    HomeScreen(),
    ControlsScreen(),
    ConversationScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();

    // Check if a dangerous action requires confirmation
    final conf = client.activeConfirmation;
    if (conf != null && !_dialogShowing) {
      _dialogShowing = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        showDialog<bool>(
          context: context,
          barrierDismissible: false,
          builder: (_) => ConfirmationModal(
            prompt: conf,
            onDecision: (confirmed) {
              Navigator.of(context, rootNavigator: true).pop();
              client.confirmAction(conf.actionName, confirmed);
              if (confirmed) {
                // Re-execute with forceConfirmed flag
                client.executeCommand(conf.actionName, forceConfirmed: true);
              }
              _dialogShowing = false;
            },
          ),
        ).then((_) {
          _dialogShowing = false;
        });
      });
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 650;
        return Scaffold(
          appBar: const AgeHeader(),
          body: Row(
            children: [
              // Left Sidebar Navigation
              NavigationRail(
                selectedIndex: _selectedIndex,
                minWidth: isCompact ? 56 : 72,
                backgroundColor: AgeTheme.darkSurface,
                indicatorColor: AgeTheme.amberAccent.withValues(alpha: 0.2),
                selectedIconTheme: const IconThemeData(color: AgeTheme.amberAccent),
                unselectedIconTheme: const IconThemeData(color: AgeTheme.textMuted),
                selectedLabelTextStyle: const TextStyle(
                  color: AgeTheme.amberAccent,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
                unselectedLabelTextStyle: const TextStyle(
                  color: AgeTheme.textMuted,
                  fontSize: 11,
                ),
                onDestinationSelected: (idx) {
                  setState(() => _selectedIndex = idx);
                },
                labelType: isCompact ? NavigationRailLabelType.none : NavigationRailLabelType.all,
                destinations: const [
                  NavigationRailDestination(
                    icon: Icon(Icons.mic_none),
                    selectedIcon: Icon(Icons.mic),
                    label: Text('Home'),
                  ),
                  NavigationRailDestination(
                    icon: Icon(Icons.tune),
                    selectedIcon: Icon(Icons.tune),
                    label: Text('Controls'),
                  ),
                  NavigationRailDestination(
                    icon: Icon(Icons.chat_bubble_outline),
                    selectedIcon: Icon(Icons.chat_bubble),
                    label: Text('History'),
                  ),
                  NavigationRailDestination(
                    icon: Icon(Icons.settings_outlined),
                    selectedIcon: Icon(Icons.settings),
                    label: Text('Settings'),
                  ),
                ],
              ),

              const VerticalDivider(thickness: 1, width: 1, color: AgeTheme.borderDark),

              // Main Screen Content
              Expanded(
                child: _screens[_selectedIndex],
              ),
            ],
          ),
        );
      },
    );
  }
}
