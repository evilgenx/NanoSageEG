# main.py

import argparse
import asyncio
import yaml
import os
import sys # Added for sys.exit

# Attempt to import google.generativeai, handle if not installed yet
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None # Define genai as None if import fails

from search_session import SearchSession

def load_config(config_path):
    """Loads configuration from a YAML file with error handling."""
    if not os.path.isfile(config_path):
        print(f"[WARN] Config file not found at {config_path}. Using defaults.", file=sys.stderr)
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f: # Added encoding
            config = yaml.safe_load(f)
            return config if config else {} # Return empty dict if file is empty or invalid YAML
    except yaml.YAMLError as e:
        print(f"[ERROR] Error parsing config file {config_path}: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"[ERROR] Unexpected error loading config file {config_path}: {e}", file=sys.stderr)
        return {}

def list_gemini_models(api_key):
    """Lists available Gemini models suitable for content generation."""
    if not GEMINI_AVAILABLE:
        print("[ERROR] google-generativeai library not installed. Cannot list models.", file=sys.stderr)
        print("Please install it: pip install google-generativeai", file=sys.stderr)
        return None
    if not api_key:
        print("[ERROR] Gemini API key not found in config. Cannot list models.", file=sys.stderr)
        print("Please add 'gemini:\n  api_key: YOUR_API_KEY' to your config.yaml", file=sys.stderr)
        return None

    try:
        genai.configure(api_key=api_key)
        print("[INFO] Fetching available Gemini models...")
        models = []
        for m in genai.list_models():
            # Check if the model supports the 'generateContent' method
            if 'generateContent' in m.supported_generation_methods:
                # Prepend 'gemini/' to the model name for consistency with rag_model argument
                # Use the model name directly as returned by the API (e.g., 'models/gemini-1.5-flash')
                models.append(f"gemini/{m.name}") # Keep the 'gemini/' prefix for user clarity
        print("\n[INFO] Found models suitable for RAG (use with --rag_model):")
        for model_name in sorted(models):
             print(f"- {model_name}")
        print("\nExample: --rag_model gemini/models/gemini-1.5-flash")
        return models
    except Exception as e:
        print(f"[ERROR] Failed to list Gemini models: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description="Multi-step RAG pipeline with depth-limited searching.")
    parser.add_argument("--query", type=str, required=True, help="Initial user query")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--corpus_dir", type=str, default=None, help="Path to local corpus folder")
    parser.add_argument("--device", type=str, default="cpu", help="Device for retrieval model (cpu or cuda)")
    parser.add_argument("--retrieval_model", type=str, choices=["colpali", "all-minilm"], default="colpali")
    parser.add_argument("--top_k", type=int, default=3, help="Number of local docs to retrieve")
    parser.add_argument("--web_search", action="store_true", default=False, help="Enable web search")
    parser.add_argument("--personality", type=str, default=None, help="Optional personality for Gemma (e.g. cheerful)")
    parser.add_argument("--rag_model", type=str, default="gemma", help="Which model to use for final RAG steps")
    parser.add_argument("--max_depth", type=int, default=1, help="Depth limit for subquery expansions")
    args = parser.parse_args()

    config = load_config(args.config)

    # Extract Gemini API key from config
    gemini_api_key = config.get("gemini", {}).get("api_key", None)

    # --- Handle Gemini Model Listing ---
    if args.rag_model == "gemini":
        print("[INFO] '--rag_model gemini' specified. Listing available models...")
        list_gemini_models(gemini_api_key)
        sys.exit(0) # Exit after listing models

    # --- Proceed with Search Session ---
    session = SearchSession(
        query=args.query,
        config=config,
        gemini_api_key=gemini_api_key, # Pass the key
        corpus_dir=args.corpus_dir,
        device=args.device,
        retrieval_model=args.retrieval_model,
        top_k=args.top_k,
        web_search_enabled=args.web_search,
        personality=args.personality,
        rag_model=args.rag_model,
        max_depth=args.max_depth
    )

    loop = asyncio.get_event_loop()
    final_answer = loop.run_until_complete(session.run_session())

    # Save final report
    output_path = session.save_report(final_answer)
    print(f"[INFO] Final report saved to: {output_path}")


if __name__ == "__main__":
    main()
