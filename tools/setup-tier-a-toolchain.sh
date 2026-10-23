#!/usr/bin/env bash
# tools/setup-tier-a-toolchain.sh — instala a toolchain REAL de um engine
# Tier A no runner de CI (ubuntu-latest) e expõe as variáveis de ambiente
# que o tools/build-tier-a.py consome (KOTLINC, GROOVY_HOME, GROOVYC,
# ANDROID_NDK, CARGO_NDK, GOMOBILE, ZIG, HAXE, GRADLE, WAT2WASM, HERMESC).
#
# Uso no workflow (o mesmo passo do build OU com GITHUB_ENV):
#   source tools/setup-tier-a-toolchain.sh engine-02-kotlin
#   python3 tools/build-tier-a.py --engine engine-02-kotlin --out dist ...
# Quando GITHUB_ENV está definido, as variáveis também são persistidas
# para os passos seguintes do job.
#
# Todos os downloads são pinados (mesma URL/versão sempre): versões fixas
# garantem builds reprodutíveis entre execuções.
set -euo pipefail

ENGINE="${1:-}"
CACHE="${RUNNER_TEMP:-/tmp}/apktester-tier-a"
mkdir -p "$CACHE"

fail() { echo "[setup-tier-a] erro: $*" >&2; exit 2; }

# setenv VAR VALOR — export imediato + persistência em GITHUB_ENV.
setenv() {
  local var="$1" val="$2"
  export "$var=$val"
  if [ -n "${GITHUB_ENV:-}" ]; then
    printf '%s=%s\n' "$var" "$val" >> "$GITHUB_ENV"
  fi
}

# add_path DIR — acrescenta ao PATH deste shell. NÃO escreve PATH no
# GITHUB_ENV: lá, PATH=... SUBSTITUI o PATH inteiro dos passos seguintes
# (quebrou o python3 do job do haxe). setup + build rodam no MESMO passo.
add_path() {
  local dir="$1"
  case ":$PATH:" in
    *":$dir:"*) : ;;
    *) PATH="$dir:$PATH"; export PATH ;;
  esac
}

fetch() { # fetch <url> <dest>
  local url="$1" dest="$2"
  if [ ! -f "$dest" ]; then
    echo "[setup-tier-a] baixando $url"
    curl -fsSL --retry 3 -o "$dest" "$url"
  fi
}

# --- Android NDK (compartilhado por 07/08/09/10/16/25/30/31) ---
ensure_ndk() {
  local ndk="${ANDROID_NDK_LATEST_HOME:-${ANDROID_NDK_HOME:-}}"
  if [ -z "$ndk" ] || [ ! -d "$ndk" ]; then
    local base="${ANDROID_HOME:-/usr/local/lib/android/sdk}"
    local d latest=""
    shopt -s nullglob
    for d in "$base"/ndk/*; do
      [ -d "$d" ] && latest="$d"
    done
    shopt -u nullglob
    ndk="$latest"
  fi
  if [ -z "$ndk" ] || [ ! -d "$ndk" ]; then
    fail "Android NDK não encontrado (instale 'ndk;27.0.12077973' via sdkmanager)"
  fi
  setenv ANDROID_NDK "$ndk"
  setenv ANDROID_NDK_HOME "$ndk"
  echo "[setup-tier-a] NDK: $ndk"
}

# --- rust (stable do runner) + cargo-ndk (compartilhado por 09/16/30/31) ---
ensure_rust() {
  local targets="$1" # ex.: "aarch64-linux-android x86_64-linux-android"
  command -v cargo >/dev/null 2>&1 || fail "cargo ausente (o workflow instala rustup/stable antes)"
  # stable do runner: wasmer-vm 7.5 e wry 0.57 exigem rust >= 1.96/1.85 —
  # a versão exata vai para o report JSON do build (rastreabilidade).
  rustup default stable
  rustup update stable >/dev/null 2>&1 || true
  local t
  for t in $targets; do
    rustup target add "$t"
  done
  ensure_ndk
  if ! command -v cargo-ndk >/dev/null 2>&1; then
    cargo install cargo-ndk --locked --version 3.5.0
  fi
  setenv CARGO_NDK "$(command -v cargo-ndk)"
  setenv RUSTC_VERSION "$(rustc --version)"
}

case "$ENGINE" in
  engine-01-java)
    : # só JDK + build-tools (já instalados pelo workflow)
    ;;

  engine-02-kotlin|engine-03-kmp)
    KOTLIN_VER=2.0.20
    fetch "https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VER}/kotlin-compiler-${KOTLIN_VER}.zip" \
      "$CACHE/kotlin-compiler-${KOTLIN_VER}.zip"
    # o zip extrai para kotlinc/ (sem sufixo): desembrulha num subdir por versão
    [ -d "$CACHE/kotlin-${KOTLIN_VER}/kotlinc" ] || unzip -q "$CACHE/kotlin-compiler-${KOTLIN_VER}.zip" -d "$CACHE/kotlin-${KOTLIN_VER}"
    setenv KOTLINC "$CACHE/kotlin-${KOTLIN_VER}/kotlinc/bin/kotlinc"
    [ -x "$KOTLINC" ] || fail "kotlinc não executável"
    ;;

  engine-06-groovy)
    GROOVY_VER=3.0.21
    fetch "https://archive.apache.org/dist/groovy/${GROOVY_VER}/distribution/apache-groovy-binary-${GROOVY_VER}.zip" \
      "$CACHE/groovy-${GROOVY_VER}.zip"
    [ -d "$CACHE/groovy-${GROOVY_VER}" ] || unzip -q "$CACHE/groovy-${GROOVY_VER}.zip" -d "$CACHE"
    setenv GROOVY_HOME "$CACHE/groovy-${GROOVY_VER}"
    setenv GROOVYC "$GROOVY_HOME/bin/groovyc"
    [ -x "$GROOVYC" ] || fail "groovyc não executável"
    ;;

  engine-07-c-ndk|engine-08-cpp-ndk)
    ensure_ndk
    ;;

  engine-09-rust)
    ensure_rust "aarch64-linux-android x86_64-linux-android"
    ;;

  engine-16-tauri)
    # Deps externas (tauri 2.12 / wry 0.57) respeitam os Cargo.lock
    # commitados — versões pinadas sem flag extra.
    ensure_rust "x86_64-linux-android"
    ;;

  engine-30-wasm-in-app)
    WABT_VER=1.0.36
    fetch "https://github.com/WebAssembly/wabt/releases/download/${WABT_VER}/wabt-${WABT_VER}-ubuntu-20.04.tar.gz" \
      "$CACHE/wabt-${WABT_VER}.tar.gz"
    [ -d "$CACHE/wabt-${WABT_VER}" ] || tar -xzf "$CACHE/wabt-${WABT_VER}.tar.gz" -C "$CACHE"
    setenv WAT2WASM "$CACHE/wabt-${WABT_VER}/bin/wat2wasm"
    [ -x "$WAT2WASM" ] || fail "wat2wasm não executável"
    ensure_rust "x86_64-linux-android"
    ;;

  engine-31-hybrid)
    # Kotlin + rust + hermes + wabt (todas as pernas do TST-14)
    KOTLIN_VER=2.0.20
    fetch "https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VER}/kotlin-compiler-${KOTLIN_VER}.zip" \
      "$CACHE/kotlin-compiler-${KOTLIN_VER}.zip"
    [ -d "$CACHE/kotlin-${KOTLIN_VER}/kotlinc" ] || unzip -q "$CACHE/kotlin-compiler-${KOTLIN_VER}.zip" -d "$CACHE/kotlin-${KOTLIN_VER}"
    setenv KOTLINC "$CACHE/kotlin-${KOTLIN_VER}/kotlinc/bin/kotlinc"
    WABT_VER=1.0.36
    fetch "https://github.com/WebAssembly/wabt/releases/download/${WABT_VER}/wabt-${WABT_VER}-ubuntu-20.04.tar.gz" \
      "$CACHE/wabt-${WABT_VER}.tar.gz"
    [ -d "$CACHE/wabt-${WABT_VER}" ] || tar -xzf "$CACHE/wabt-${WABT_VER}.tar.gz" -C "$CACHE"
    setenv WAT2WASM "$CACHE/wabt-${WABT_VER}/bin/wat2wasm"
    HERMES_VER=0.11.0
    fetch "https://registry.npmjs.org/hermes-engine/-/hermes-engine-${HERMES_VER}.tgz" \
      "$CACHE/hermes-engine-${HERMES_VER}.tgz"
    [ -d "$CACHE/package" ] || tar -xzf "$CACHE/hermes-engine-${HERMES_VER}.tgz" -C "$CACHE"
    setenv HERMESC "$CACHE/package/linux64-bin/hermesc"
    [ -x "$HERMESC" ] || fail "hermesc não executável"
    ensure_rust "x86_64-linux-android"
    ;;

  engine-10-go)
    GO_VER=1.23.4
    if ! command -v go >/dev/null 2>&1; then
      fetch "https://go.dev/dl/go${GO_VER}.linux-amd64.tar.gz" "$CACHE/go${GO_VER}.tar.gz"
      if [ ! -d /usr/local/go ]; then
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf "$CACHE/go${GO_VER}.tar.gz"
      fi
      add_path /usr/local/go/bin
    fi
    GOMOBILE_VERSION="v0.0.0-20261011034528-197770444867"
    go install "golang.org/x/mobile/cmd/gomobile@${GOMOBILE_VERSION}"
    go install "golang.org/x/mobile/cmd/gobind@${GOMOBILE_VERSION}"
    add_path "$(go env GOPATH)/bin"
    setenv GOMOBILE "$(command -v gomobile)"
    gomobile init
    # o módulo gobind requer golang.org/x/mobile (bind gera imports do
    # bridge) — tidy resolve o go.sum no runner
    GOBIND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../suites/engines/engine-10-go/gobind" && pwd)"
    (cd "$GOBIND_DIR" && go mod tidy)
    ensure_ndk
    ;;

  engine-12-zig)
    ZIG_VER=0.13.0
    fetch "https://ziglang.org/download/${ZIG_VER}/zig-linux-x86_64-${ZIG_VER}.tar.xz" \
      "$CACHE/zig-${ZIG_VER}.tar.xz"
    [ -d "$CACHE/zig-linux-x86_64-${ZIG_VER}" ] || tar -xJf "$CACHE/zig-${ZIG_VER}.tar.xz" -C "$CACHE"
    setenv ZIG "$CACHE/zig-linux-x86_64-${ZIG_VER}/zig"
    [ -x "$ZIG" ] || fail "zig não executável"
    ;;

  engine-24-haxe)
    HAXE_VER=4.3.6
    fetch "https://github.com/HaxeFoundation/haxe/releases/download/${HAXE_VER}/haxe-${HAXE_VER}-linux64.tar.gz" \
      "$CACHE/haxe-${HAXE_VER}.tar.gz"
    # o tarball extrai para haxe_<buildid>/: localiza a raiz única
    mkdir -p "$CACHE/haxe-${HAXE_VER}"
    HAXE_BIN="$(find "$CACHE/haxe-${HAXE_VER}" -maxdepth 2 -name haxe -type f 2>/dev/null | head -1)"
    if [ -z "$HAXE_BIN" ]; then
      tar -xzf "$CACHE/haxe-${HAXE_VER}.tar.gz" -C "$CACHE/haxe-${HAXE_VER}"
      HAXE_BIN="$(find "$CACHE/haxe-${HAXE_VER}" -maxdepth 2 -name haxe -type f | head -1)"
    fi
    HAXE_DIR="$(dirname "$HAXE_BIN")"
    [ -n "$HAXE_DIR" ] || fail "raiz do tarball haxe não encontrada"
    setenv HAXE "$HAXE_DIR/haxe"
    setenv HAXE_STD_PATH "$HAXE_DIR/std"
    [ -x "$HAXE" ] || fail "haxe não executável"
    add_path "$HAXE_DIR"
    # ant (hxjava usa build.xml) + neko (o haxelib do tarball é binário
    # neko: libneko.so.2) + haxelib/hxjava
    if ! command -v ant >/dev/null 2>&1 || ! ldconfig -p 2>/dev/null | grep -q libneko.so; then
      sudo apt-get update -qq
      sudo apt-get install -y -qq ant neko >/dev/null
    fi
    "$HAXE" --version
    # o repositório de libs NÃO pode ser $HOME/.haxelib (reservado ao
    # arquivo de config do haxelib)
    "$HAXE_DIR/haxelib" setup "$CACHE/haxelib-repo"
    "$HAXE_DIR/haxelib" install hxjava --always >/dev/null
    ;;

  engine-25-python-chaquopy)
    GRADLE_VER=8.10.2
    fetch "https://services.gradle.org/distributions/gradle-${GRADLE_VER}-bin.zip" \
      "$CACHE/gradle-${GRADLE_VER}-bin.zip"
    [ -d "$CACHE/gradle-${GRADLE_VER}" ] || unzip -q "$CACHE/gradle-${GRADLE_VER}-bin.zip" -d "$CACHE"
    setenv GRADLE "$CACHE/gradle-${GRADLE_VER}/bin/gradle"
    [ -x "$GRADLE" ] || fail "gradle não executável"
    ensure_ndk
    ;;

  "")
    fail "uso: tools/setup-tier-a-toolchain.sh <engine-dir>"
    ;;

  *)
    fail "engine desconhecido: $ENGINE (não é Tier A)"
    ;;
esac

echo "[setup-tier-a] toolchain de $ENGINE pronta"
