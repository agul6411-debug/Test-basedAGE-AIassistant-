import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core_client.dart';
import '../theme.dart';
import '../widgets/settings_dialog.dart';
import '../widgets/voice_orb.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _inputCtrl = TextEditingController();
  final ScrollController _historyScrollCtrl = ScrollController();

  @override
  void dispose() {
    _inputCtrl.dispose();
    _historyScrollCtrl.dispose();
    super.dispose();
  }

  void _submitCommand(CoreClient client) {
    final text = _inputCtrl.text.trim();
    if (text.isNotEmpty) {
      client.executeCommand(text);
      _inputCtrl.clear();
    }
  }

  @override
  Widget build(BuildContext context) {
    final client = context.watch<CoreClient>();
    final isGroqActive = client.isGroqConfigured;
    final recent = client.status.recentCommands;

    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= 900;

        return Scaffold(
          backgroundColor: Colors.transparent,
          body: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Top Groq Banner (if not yet configured)
                if (!isGroqActive) ...[
                  _buildGroqSetupBanner(context),
                  const SizedBox(height: 14),
                ],

                // 2. Main Body Content (Responsive Split)
                Expanded(
                  child: isWide
                      ? Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Left Column: Voice Orb & Interactive Prompts
                            Expanded(
                              flex: 5,
                              child: SingleChildScrollView(
                                child: Column(
                                  children: [
                                    const SizedBox(height: 10),
                                    VoiceOrb(
                                      activeState: client.activeState,
                                      onTap: () => client.toggleListening(),
                                      size: 210,
                                    ),
                                    const SizedBox(height: 24),
                                    _buildInspirationChips(client),
                                    const SizedBox(height: 20),
                                    _buildTypedInputBar(client),
                                  ],
                                ),
                              ),
                            ),

                            const SizedBox(width: 24),

                            // Right Column: Live Conversation Stream
                            Expanded(
                              flex: 4,
                              child: _buildConversationPanel(context, client, recent),
                            ),
                          ],
                        )
                      : SingleChildScrollView(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              const SizedBox(height: 10),
                              Center(
                                child: VoiceOrb(
                                  activeState: client.activeState,
                                  onTap: () => client.toggleListening(),
                                  size: 190,
                                ),
                              ),
                              const SizedBox(height: 20),
                              _buildTypedInputBar(client),
                              const SizedBox(height: 16),
                              _buildInspirationChips(client),
                              const SizedBox(height: 20),
                              SizedBox(
                                height: 380,
                                child: _buildConversationPanel(context, client, recent),
                              ),
                            ],
                          ),
                        ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  /// Banner guiding user to enter their free Groq API key for zero load & cloud chat
  Widget _buildGroqSetupBanner(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AgeTheme.amberAccent.withValues(alpha: 0.18),
            const Color(0xFF8B5CF6).withValues(alpha: 0.14),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AgeTheme.amberAccent.withValues(alpha: 0.4),
          width: 1.2,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AgeTheme.amberAccent.withValues(alpha: 0.25),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.bolt, color: AgeTheme.amberAccent, size: 20),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Supercharge AGE with Free Groq Cloud AI',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: AgeTheme.textPrimary,
                  ),
                ),
                Text(
                  'Enjoy real-time Roman Urdu & English conversations with 0% CPU/RAM load and ultra-low latency (<0.5s).',
                  style: TextStyle(fontSize: 11, color: AgeTheme.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          ElevatedButton.icon(
            onPressed: () => GroqSettingsDialog.show(context),
            icon: const Icon(Icons.key, size: 16),
            label: const Text('Setup Key', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
            style: ElevatedButton.styleFrom(
              backgroundColor: AgeTheme.amberAccent,
              foregroundColor: Colors.black,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            ),
          ),
        ],
      ),
    );
  }

  /// Quick conversational inspiration chips (Urdu chat, knowledge, system commands)
  Widget _buildInspirationChips(CoreClient client) {
    return Column(
      children: [
        const Text(
          'Try asking or commanding:',
          style: TextStyle(color: AgeTheme.textMuted, fontSize: 12, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          alignment: WrapAlignment.center,
          children: [
            _PromptChip(
              icon: Icons.chat_bubble_outline,
              label: 'Mujhe koi dilchasp baat batao',
              onTap: () => client.executeCommand('Mujhe koi dilchasp baat batao'),
            ),
            _PromptChip(
              icon: Icons.public,
              label: 'Dunya ka sab se bara samandar?',
              onTap: () => client.executeCommand('Dunya ka sab se bara samandar konsa hai?'),
            ),
            _PromptChip(
              icon: Icons.auto_awesome,
              label: 'Ek motivational baat sunao',
              onTap: () => client.executeCommand('Mujhe koi motivational quote sunao'),
            ),
            _PromptChip(
              icon: Icons.code,
              label: 'Python list vs tuple',
              onTap: () => client.executeCommand('Python mein list aur tuple mein kya farq hai?'),
            ),
            _PromptChip(
              icon: Icons.apps,
              label: 'open chrome',
              onTap: () => client.executeCommand('open chrome'),
            ),
            _PromptChip(
              icon: Icons.volume_up,
              label: 'volume up',
              onTap: () => client.executeCommand('volume up'),
            ),
            _PromptChip(
              icon: Icons.desktop_windows,
              label: 'save my desktop',
              onTap: () => client.executeCommand('save my desktop'),
            ),
          ],
        ),
      ],
    );
  }

  /// Sleek floating typed command & conversation input bar
  Widget _buildTypedInputBar(CoreClient client) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      decoration: BoxDecoration(
        color: AgeTheme.darkCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AgeTheme.borderDark, width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          IconButton(
            icon: Icon(
              client.activeState == 'listening' ? Icons.mic : Icons.mic_none,
              color: client.activeState == 'listening' ? AgeTheme.amberAccent : AgeTheme.textMuted,
            ),
            tooltip: 'Toggle Voice Listening',
            onPressed: () => client.toggleListening(),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: TextField(
              controller: _inputCtrl,
              onSubmitted: (_) => _submitCommand(client),
              style: const TextStyle(color: AgeTheme.textPrimary, fontSize: 14),
              decoration: const InputDecoration(
                hintText: 'Ask AGE anything or type an OS command...',
                hintStyle: TextStyle(color: AgeTheme.textMuted, fontSize: 13),
                border: InputBorder.none,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.arrow_upward_rounded, color: AgeTheme.amberAccent, size: 22),
            tooltip: 'Send prompt',
            onPressed: () => _submitCommand(client),
          ),
        ],
      ),
    );
  }

  /// Real-time conversation stream and recent command responses
  Widget _buildConversationPanel(BuildContext context, CoreClient client, List<dynamic> recent) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AgeTheme.borderDark, width: 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Panel Header
            Row(
              children: [
                const Icon(Icons.forum_outlined, color: AgeTheme.amberAccent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Live Conversation Stream',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: AgeTheme.textPrimary,
                        ),
                  ),
                ),
                if (recent.isNotEmpty)
                  IconButton(
                    icon: const Icon(Icons.delete_sweep, size: 18, color: AgeTheme.textMuted),
                    tooltip: 'Clear Chat Memory Buffer',
                    onPressed: () {
                      client.clearMemory();
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Chat memory buffer cleared.'),
                          backgroundColor: AgeTheme.amberAccent,
                          duration: Duration(seconds: 2),
                        ),
                      );
                    },
                  ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: client.isGroqConfigured
                        ? AgeTheme.mintSuccess.withValues(alpha: 0.12)
                        : AgeTheme.borderDark,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    client.isGroqConfigured ? 'Groq LLaMA 3.3' : 'Local Brain',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: client.isGroqConfigured ? AgeTheme.mintSuccess : AgeTheme.textMuted,
                    ),
                  ),
                ),
              ],
            ),

            const Divider(color: AgeTheme.borderDark, height: 20),

            // Conversation Messages List
            Expanded(
              child: recent.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.chat_bubble_outline, size: 40, color: AgeTheme.textMuted.withValues(alpha: 0.5)),
                          const SizedBox(height: 12),
                          const Text(
                            'No conversation yet.\nTap the orb or type below to speak with AGE!',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: AgeTheme.textMuted, fontSize: 13, height: 1.4),
                          ),
                        ],
                      ),
                    )
                  : ListView.separated(
                      controller: _historyScrollCtrl,
                      itemCount: recent.length,
                      separatorBuilder: (context, index) => const SizedBox(height: 10),
                      itemBuilder: (context, index) {
                        final item = recent[index];
                        final isBrain = item.action == 'groq_chat' || item.action == 'ollama_chat' || item.action == 'command';
                        final isSuccess = item.success == true;

                        return Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AgeTheme.darkSurface,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSuccess
                                  ? (isBrain ? AgeTheme.mintSuccess.withValues(alpha: 0.25) : AgeTheme.amberAccent.withValues(alpha: 0.25))
                                  : AgeTheme.dangerRed.withValues(alpha: 0.25),
                              width: 1,
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(
                                    isBrain ? Icons.auto_awesome : Icons.terminal,
                                    size: 14,
                                    color: isBrain ? AgeTheme.mintSuccess : AgeTheme.amberAccent,
                                  ),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      item.action.toUpperCase(),
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: isBrain ? AgeTheme.mintSuccess : AgeTheme.amberAccent,
                                      ),
                                    ),
                                  ),
                                  Text(
                                    _formatTimestamp(item.timestamp),
                                    style: const TextStyle(fontSize: 10, color: AgeTheme.textMuted),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.copy, size: 14, color: AgeTheme.textMuted),
                                    tooltip: 'Copy response',
                                    padding: EdgeInsets.zero,
                                    constraints: const BoxConstraints(),
                                    onPressed: () {
                                      Clipboard.setData(ClipboardData(text: item.result));
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(
                                          content: Text('Copied to clipboard.'),
                                          duration: Duration(seconds: 1),
                                        ),
                                      );
                                    },
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                item.result.isNotEmpty ? item.result : '(No response text)',
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: AgeTheme.textPrimary,
                                  height: 1.35,
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatTimestamp(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final h = dt.hour.toString().padLeft(2, '0');
      final m = dt.minute.toString().padLeft(2, '0');
      final s = dt.second.toString().padLeft(2, '0');
      return '$h:$m:$s';
    } catch (_) {
      return '';
    }
  }
}

class _PromptChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _PromptChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: AgeTheme.darkSurface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AgeTheme.borderDark),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: AgeTheme.amberAccent),
            const SizedBox(width: 6),
            Text(
              label,
              style: const TextStyle(fontSize: 12, color: AgeTheme.textSecondary, fontWeight: FontWeight.w500),
            ),
          ],
        ),
      ),
    );
  }
}
