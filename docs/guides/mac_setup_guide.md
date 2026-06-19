# 🛠️ Fina Agent Workstation Setup Guide

This guide describes the step-by-step setup required to run and test the `fina-agent` codebase on a new MacBook (2026).

> **Machine**: Brand new MacBook (2026)  
> **Repository**: `fina-agent` (Python agent pipeline)  
> **Package manager**: Homebrew  
> **Editor**: VS Code + Google Antigravity 2.0  
> **Shell**: zsh + Starship prompt  

---

## Phase 1 — System Foundations

### Step 1: Install Xcode Command Line Tools

```bash
xcode-select --install
```

---

### Step 2: Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Add to your PATH:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

---

### Step 3: Install Starship Prompt

```bash
brew install starship
echo 'eval "$(starship init zsh)"' >> ~/.zshrc
source ~/.zshrc
```

---

### Step 4: Install Google Chrome

Required for Chrome DevTools MCP browser automation and verification.

```bash
brew install --cask google-chrome
```

---

## Phase 2 — Runtimes & Dev Tools

### Step 5: Install Python 3.11

```bash
brew install python@3.11
```

Set Python 3.11 as default in your shell config:
```bash
echo 'alias python3=python3.11' >> ~/.zshrc
source ~/.zshrc
```

---

### Step 6: Install Node.js (for Chrome DevTools MCP)

Node.js (which includes `npm` and `npx`) is required to run the Chrome DevTools MCP server (`chrome_devtools`), which is used by the search and enrichment subagents.

```bash
brew install node
```

---

### Step 7: Install Google Cloud SDK

Required to set up credentials for connecting to the database.

```bash
brew install --cask google-cloud-sdk
```

Add gcloud to your shell:
```bash
echo 'source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"' >> ~/.zshrc
echo 'source "$(brew --prefix)/share/google-cloud-sdk/completion.zsh.inc"' >> ~/.zshrc
source ~/.zshrc
```

---

### Step 8: Install GitHub CLI & Authenticate

```bash
brew install gh
gh auth login
```
Select **GitHub.com**, **HTTPS**, and **Login with a web browser**.

Configure git identity:
```bash
git config --global user.name "Ryan"
git config --global user.email "your-email@example.com"
```

---

## Phase 3 — Google Antigravity 2.0

### Step 9: Install the Antigravity CLI (`agy`)

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Add to your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Step 10: Authenticate Antigravity

Run `agy` to trigger Google account OAuth via browser:
```bash
agy
```
Authenticate and then exit with `/exit` or `Ctrl+C`.

---

## Phase 4 — Repository Setup & Configuration

### Step 11: Clone the Repository

```bash
mkdir -p ~/src && cd ~/src
gh repo clone deriveraryan/fina-agent
```

---

### Step 12: Set Up Python Virtual Environment & Playwright

```bash
cd ~/src/fina-agent
python3.11 -m venv .venv
source .venv/bin/activate

# Install requirements + Antigravity Python SDK
pip install -r requirements.txt
pip install google-antigravity

# Post-Install: Install Playwright & Crawl4AI browser binaries
python3 -m playwright install chromium
crawl4ai-setup
```

Verify browser setup:
```bash
crawl4ai-doctor
```

---

### Step 13: Authenticate Google Cloud (ADC)

This grants the local Python scripts OAuth2 credentials to call the Fina PostgreSQL GraphQL endpoints:

```bash
gcloud auth login
gcloud config set project fina-au
gcloud auth application-default login
```

---

### Step 14: Create Environment Configuration

```bash
cd ~/src/fina-agent
cp .env.example .env
```

Edit `.env` to include your actual API keys:

```bash
# ~/src/fina-agent/.env
GCP_PROJECT=fina-au
GOOGLE_CLOUD_PROJECT=fina-au
GOOGLE_CLOUD_QUOTA_PROJECT=fina-au

# Google Maps API key
GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>

# Gemini API key
GEMINI_API_KEY=<your-gemini-api-key>

# SMTP Configuration (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<your-email@gmail.com>
SMTP_PASSWORD=<your-app-password>
```

---

## Phase 5 — Initialize Workspace & Verify

### Step 15: Launch Antigravity TUI

Initialize the workspace and inspect loaded skills:
```bash
cd ~/src/fina-agent
agy
```
Inside the TUI, run:
```text
agy inspect
```
Verify that the `fina-agent` skills and configs are loaded successfully. Exit with `/exit`.

---

### Step 16: Run Offline Unit Tests

Validate that the setup is functional by running the test suite:

> [!IMPORTANT]
> The Fina constitution mandates that all tests must run **100% offline & mocked**. Do not run emulators or cloud connections while running tests.

```bash
cd ~/src/fina-agent
source .venv/bin/activate
python3 -m unittest discover tests
```

---

## 📋 Quick Reference — PATH Additions in `~/.zshrc`

```bash
# ~/.zshrc additions summary

# Homebrew (Apple Silicon)
eval "$(/opt/homebrew/bin/brew shellenv)"

# Starship prompt
eval "$(starship init zsh)"

# Google Cloud SDK
source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"
source "$(brew --prefix)/share/google-cloud-sdk/completion.zsh.inc"

# Google Antigravity CLI
export PATH="$HOME/.local/bin:$PATH"

# Python 3.11 alias
alias python3=python3.11
```
