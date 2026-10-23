// engine-13-flutter — Tier B (A7), seed 20261022.
// Build real: flutter create (android) + flutter build apk --release
// --target-platform android-x64 com o Flutter SDK 3.24.5 estavel.
import 'package:flutter/material.dart';

void main() {
  runApp(const Engine13App());
}

class Engine13App extends StatelessWidget {
  const Engine13App({super.key});

  static const int seed = 20261022;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'APK Tester engine-13-flutter',
      home: Scaffold(
        appBar: AppBar(title: const Text('engine-13-flutter')),
        body: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Text('seed: $seed'),
              SizedBox(height: 12),
              Text('deteccao nao valida payload nem autoriza execucao'),
            ],
          ),
        ),
      ),
    );
  }
}
