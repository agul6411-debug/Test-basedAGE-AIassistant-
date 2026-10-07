import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AgeTheme {
  // Brand color palette
  static const Color darkBg = Color(0xFF121212);
  static const Color darkSurface = Color(0xFF1E1E1E);
  static const Color darkCard = Color(0xFF262626);
  static const Color borderDark = Color(0xFF333333);

  static const Color amberAccent = Color(0xFFFFB547); // Mic / Primary Accent
  static const Color mintSuccess = Color(0xFF5EEAD4); // Success / Speaking
  static const Color dangerRed = Color(0xFFEF4444);   // Emergency Stop / Dangerous
  static const Color textPrimary = Color(0xFFF3F4F6);
  static const Color textSecondary = Color(0xFF9CA3AF);
  static const Color textMuted = Color(0xFF6B7280);

  static ThemeData get darkTheme {
    final baseTextTheme = Typography.material2021().white;

    final soraHeadings = GoogleFonts.soraTextTheme(baseTextTheme);
    final plexBody = GoogleFonts.ibmPlexSansTextTheme(baseTextTheme);

    final mergedTextTheme = plexBody.copyWith(
      displayLarge: soraHeadings.displayLarge?.copyWith(fontWeight: FontWeight.bold, color: textPrimary),
      displayMedium: soraHeadings.displayMedium?.copyWith(fontWeight: FontWeight.bold, color: textPrimary),
      displaySmall: soraHeadings.displaySmall?.copyWith(fontWeight: FontWeight.w600, color: textPrimary),
      headlineLarge: soraHeadings.headlineLarge?.copyWith(fontWeight: FontWeight.w700, color: textPrimary),
      headlineMedium: soraHeadings.headlineMedium?.copyWith(fontWeight: FontWeight.w600, color: textPrimary),
      headlineSmall: soraHeadings.headlineSmall?.copyWith(fontWeight: FontWeight.w600, color: textPrimary),
      titleLarge: soraHeadings.titleLarge?.copyWith(fontWeight: FontWeight.w600, color: textPrimary),
      titleMedium: soraHeadings.titleMedium?.copyWith(fontWeight: FontWeight.w500, color: textPrimary),
      titleSmall: soraHeadings.titleSmall?.copyWith(fontWeight: FontWeight.w500, color: textSecondary),
      bodyLarge: plexBody.bodyLarge?.copyWith(color: textPrimary),
      bodyMedium: plexBody.bodyMedium?.copyWith(color: textSecondary),
      bodySmall: plexBody.bodySmall?.copyWith(color: textMuted),
    );

    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: darkBg,
      primaryColor: amberAccent,
      cardColor: darkCard,
      colorScheme: const ColorScheme.dark(
        primary: amberAccent,
        secondary: mintSuccess,
        error: dangerRed,
        surface: darkSurface,
      ),
      textTheme: mergedTextTheme,
      cardTheme: CardThemeData(
        color: darkCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: borderDark, width: 1),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: darkSurface,
        elevation: 0,
        centerTitle: false,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: amberAccent,
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: borderDark),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
    );
  }
}
