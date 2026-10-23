"""
Standalone diagnostic tool to test all your AI provider keys directly.
Usage:
  python test_keys.py
"""

import os
import sys
import json
import requests

try:
    from groq import Groq
except ImportError:
    Groq = None

# Try loading .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def collect_keys(prefix, count=10):
    keys = []
    single = os.getenv(prefix)
    if single and single.strip():
        for k in single.split(","):
            if k.strip() and k.strip() not in keys:
                keys.append(k.strip())
    plural = os.getenv(f"{prefix}S")
    if plural and plural.strip():
        for k in plural.split(","):
            if k.strip() and k.strip() not in keys:
                keys.append(k.strip())
    for i in range(1, count + 1):
        k = os.getenv(f"{prefix}_{i}")
        if k and k.strip() and k.strip() not in keys:
            keys.append(k.strip())
    return keys

def mask(key):
    if len(key) <= 8:
        return "****"
    return key[:4] + "..." + key[-4:]

def test_groq(key):
    models_to_test = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
    last_err = ""
    for model in models_to_test:
        try:
            client = Groq(api_key=key, timeout=10.0)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            return "SUCCESS", f"Model: {model} responded: '{resp.choices[0].message.content.strip()}'"
        except Exception as e:
            last_err = str(e)
            if "model" in last_err.lower() or "404" in last_err:
                continue
            return "FAILED", last_err[:120]
    return "FAILED", last_err[:120]

def test_gemini(key):
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = ""
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": "ping"}]}], "generationConfig": {"maxOutputTokens": 5}}
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return "SUCCESS", f"Model: {model} responded: '{text}'"
            elif r.status_code == 404:
                last_err = f"404 not found ({model})"
                continue
            else:
                return "FAILED", f"Status {r.status_code}: {r.text[:100]}"
        except Exception as e:
            last_err = str(e)
    return "FAILED", last_err[:120]

def test_cerebras(key):
    models = ["gpt-oss-120b", "qwen-3.8-27b", "llama3.1-8b"]
    last_err = ""
    for model in models:
        try:
            r = requests.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                timeout=10
            )
            if r.status_code == 200:
                ans = r.json()["choices"][0]["message"]["content"].strip()
                return "SUCCESS", f"Model: {model} responded: '{ans}'"
            elif r.status_code == 404:
                last_err = f"404 model not found ({model})"
                continue
            else:
                return "FAILED", f"Status {r.status_code}: {r.text[:100]}"
        except Exception as e:
            last_err = str(e)
    return "FAILED", last_err[:120]

def test_openrouter(key):
    models = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "liquid/lfm-2.5-2.6b:free",
    ]
    last_err = ""
    for model in models:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                timeout=12
            )
            if r.status_code == 200:
                ans = r.json()["choices"][0]["message"]["content"].strip()
                return "SUCCESS", f"Model: {model} responded: '{ans}'"
            else:
                last_err = f"Status {r.status_code}: {r.text[:100]}"
                continue
        except Exception as e:
            last_err = str(e)
    return "FAILED", last_err[:120]

def test_sambanova(key):
    models = ["Meta-Llama-3.3-70B-Instruct", "Qwen2.5-72B-Instruct", "Meta-Llama-3.1-8B-Instruct"]
    last_err = ""
    for model in models:
        try:
            r = requests.post(
                "https://api.sambanova.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                timeout=12
            )
            if r.status_code == 200:
                ans = r.json()["choices"][0]["message"]["content"].strip()
                return "SUCCESS", f"Model: {model} responded: '{ans}'"
            else:
                last_err = f"Status {r.status_code}: {r.text[:100]}"
                continue
        except Exception as e:
            last_err = str(e)
    return "FAILED", last_err[:120]

def test_tavily(key):
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": key, "query": "ping", "max_results": 1},
            timeout=10
        )
        if r.status_code == 200:
            return "SUCCESS", "Tavily search API responded 200 OK"
        return "FAILED", f"Status {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return "FAILED", str(e)[:120]

def main():
    print("=" * 60)
    print("      BrainyAI Provider & API Key Diagnostic Test       ")
    print("=" * 60)

    providers = [
        ("Groq", "GROQ_API_KEY", test_groq),
        ("Gemini", "GEMINI_API_KEY", test_gemini),
        ("SambaNova", "SAMBANOVA_API_KEY", test_sambanova),
        ("Cerebras", "CEREBRAS_API_KEY", test_cerebras),
        ("OpenRouter", "OPENROUTER_API_KEY", test_openrouter),
        ("Tavily", "TAVILY_API_KEY", test_tavily),
    ]

    total_keys = 0
    found_any = False

    for name, prefix, test_fn in providers:
        keys = collect_keys(prefix, 10)
        total_keys += len(keys)
        print(f"\n[*] Testing {name} ({len(keys)} key(s) detected in environment):")
        if not keys:
            print(f"    No keys found in environment for {prefix} (or {prefix}_1..N)")
            continue
        found_any = True
        for idx, key in enumerate(keys, 1):
            status, detail = test_fn(key)
            tag = "[OK]" if status == "SUCCESS" else ("[SKIP]" if status == "SKIPPED" else "[ERR]")
            clean_detail = detail.encode("ascii", "replace").decode("ascii")
            print(f"   [{idx}] {mask(key)}: {tag} {status} -> {clean_detail}")

    print("\n" + "=" * 60)
    if not found_any:
        print("NOTE: No API keys were detected in your local environment.")
        print("\nYou can either:")
        print("  1. Create a '.env' file in C:\\Users\\Shrey\\Desktop\\BrainyAi with your keys:")
        print("     GROQ_API_KEY_1=gsk_...")
        print("     GEMINI_API_KEY_1=AIzaSy...")
        print("     CEREBRAS_API_KEY_1=csk-...")
        print("  2. Or run with direct parameters:")
        print("     python test_keys.py --groq gsk_... --gemini AIzaSy... --cerebras csk-...")
        print("=" * 60)
        
        # Check command line flags
        import argparse
        parser = argparse.ArgumentParser(description="Test API keys directly")
        parser.add_argument("--groq", help="Test a Groq API key")
        parser.add_argument("--gemini", help="Test a Gemini API key")
        parser.add_argument("--cerebras", help="Test a Cerebras API key")
        parser.add_argument("--openrouter", help="Test an OpenRouter API key")
        args = parser.parse_args()

        if args.groq:
            st, msg = test_groq(args.groq)
            print(f"[Groq] {st} -> {msg}")
        if args.gemini:
            st, msg = test_gemini(args.gemini)
            print(f"[Gemini] {st} -> {msg}")
        if args.cerebras:
            st, msg = test_cerebras(args.cerebras)
            print(f"[Cerebras] {st} -> {msg}")
        if args.openrouter:
            st, msg = test_openrouter(args.openrouter)
            print(f"[OpenRouter] {st} -> {msg}")

if __name__ == "__main__":
    main()
