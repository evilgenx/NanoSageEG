# aggregator.py

import os
# Removed incorrect import: import asciidocpy

def _write_markdown_report(report_data, file_path):
    """Writes the report data to a file in Markdown format."""
    with open(file_path, "w", encoding="utf-8") as f:
        for section in report_data:
            level = section.get("level", 1)
            title = section.get("title", "")
            content = section.get("content", "")

            if title:
                f.write(f"{'#' * level} {title}\n\n")

            if isinstance(content, list): # Handle lists (e.g., search results)
                for item in content:
                    f.write(f"- {item}\n")
                f.write("\n")
            elif isinstance(content, dict): # Handle structured items (e.g., web results)
                 for item in content.get('items', []):
                    f.write(f"- **{content.get('item_prefix', 'URL')}:** {item.get('primary', '')}\n")
                    if item.get('secondary'):
                        f.write(f"  - **{content.get('secondary_prefix', 'Snippet')}:** {item.get('secondary', '')}\n")
                    if item.get('tertiary'):
                         f.write(f"  - **{content.get('tertiary_prefix', 'Tertiary')}:** {item.get('tertiary', '')}\n")
                    f.write("\n")
            elif content:
                f.write(f"{content.strip()}\n\n")
            elif title: # Write something if only title exists
                 f.write("_No content for this section._\n\n")


def _write_asciidoc_report(report_data, file_path):
    """Writes the report data to a file in AsciiDoc format."""
    adoc_lines = []
    first_h1_skipped = False

    # Find the first H1 title for the document title
    first_h1_title = next((s['title'] for s in report_data if s.get('level') == 1), None)
    if first_h1_title:
        adoc_lines.append(f"= {first_h1_title}\n")

    for section in report_data:
        level = section.get("level", 1)
        title = section.get("title", "")
        content = section.get("content", "")

        # Skip rendering the first H1 title again, but process its content
        if level == 1 and title == first_h1_title and not first_h1_skipped:
            first_h1_skipped = True
            # Process content even if title is skipped
        elif title:
             # AsciiDoc uses == for H1 (level 1 in data -> ==), === for H2 (level 2 -> ===), etc.
            adoc_lines.append(f"{'=' * (level + 1)} {title}\n")

        # Process content regardless of whether the title was skipped (for first H1) or rendered
        if isinstance(content, list):
            for item in content:
                adoc_lines.append(f"* {item}")
            adoc_lines.append("") # Add blank line after list
        elif isinstance(content, dict):
            items = content.get('items', [])
            if items:
                for item in items:
                    primary = item.get('primary', '')
                    secondary = item.get('secondary', '')
                    tertiary = item.get('tertiary', '')
                    # Use AsciiDoc labeled lists for structure
                    adoc_lines.append(f"{content.get('item_prefix', 'URL')}:: {primary}")
                    if secondary:
                        adoc_lines.append(f"{content.get('secondary_prefix', 'Snippet')}::: {secondary}")
                    if tertiary:
                         adoc_lines.append(f"{content.get('tertiary_prefix', 'Tertiary')}:::: {tertiary}")
                    adoc_lines.append("") # Blank line between items
            elif isinstance(content, str): # Handle case where content is a simple string like "_No results_"
                 adoc_lines.append(f"{content.strip()}\n")

        elif content:
             # Basic emphasis conversion: **bold** -> *bold*, _italic_ -> _italic_
             content_adoc = content.strip().replace('**', '*')
             adoc_lines.append(f"{content_adoc}\n")
        elif title and not (level == 1 and title == first_h1_title and first_h1_skipped): # Add placeholder if title exists but no content (and not the skipped H1)
             adoc_lines.append("_No content for this section._\n")


    # Write the generated lines to the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(adoc_lines))


def aggregate_results(query_id, enhanced_query, web_results, local_results, final_answer, config,
                     grouped_web_results=None, previous_results=None, follow_up_conversation=None):
    """
    Generates reports in Markdown and AsciiDoc formats.

    Writes four files:
      1) final_report.md - Contains only the final RAG answer (Markdown).
      2) final_report.adoc - Contains only the final RAG answer (AsciiDoc).
      3) <query_id>_output.md - Overall aggregator info (Markdown).
      4) <query_id>_output.adoc - Overall aggregator info (AsciiDoc).
    """
    base_dir = config.get("results_base_dir", "results")
    output_dir = os.path.join(base_dir, query_id)
    os.makedirs(output_dir, exist_ok=True)

    # --- Build Structured Report Data ---

    # 1. Final Report Data (Just the answer)
    final_report_data = [
        {"level": 1, "title": "Final Aggregated Answer (RAG)", "content": final_answer}
    ]

    # 2. Aggregator Report Data (Full details)
    aggregator_report_data = [
        {"level": 1, "title": f"Aggregated Results for Query ID: {query_id}"},
        {"level": 2, "title": "Enhanced Query", "content": enhanced_query},
        {"level": 1, "title": "Final Aggregated Answer (RAG)", "content": final_answer},
    ]

    # Web Search Results Section
    web_section_content = {"items": [], "item_prefix": "URL", "secondary_prefix": "Snippet"}
    if web_results:
        for item in web_results:
            web_section_content["items"].append({
                "primary": item.get('url', ''),
                "secondary": item.get('snippet', '')
            })
    else:
        web_section_content = "_No web results found_" # Simple string if no results
    aggregator_report_data.append({"level": 2, "title": "Web Search Results", "content": web_section_content})


    # Grouped Web Results Section
    if grouped_web_results:
        grouped_section = {"level": 2, "title": "Grouped Web Results by Domain", "content": []} # Content will be sub-sections
        for domain, items in grouped_web_results.items():
             domain_content = {
                 "items": [],
                 "item_prefix": "URL",
                 "secondary_prefix": "File Path",
                 "tertiary_prefix": "Content Type"
             }
             for item in items:
                 domain_content["items"].append({
                     "primary": item.get('url', ''),
                     "secondary": item.get('file_path', ''),
                     "tertiary": item.get('content_type', '')
                 })
             # Add a sub-section for each domain
             grouped_section["content"].append({"level": 3, "title": f"Domain: {domain}", "content": domain_content})
        aggregator_report_data.append(grouped_section)


    # Local Retrieval Results Section
    local_section_content = {"items": [], "item_prefix": "File", "secondary_prefix": "Page", "tertiary_prefix": "Snippet"}
    if local_results:
        for doc in local_results:
            meta = doc.get('metadata', {})
            item_data = {"primary": meta.get('file_path', '')}
            if 'page' in meta:
                 item_data["secondary"] = meta.get('page')
                 item_data["tertiary"] = meta.get('snippet', '') # Snippet becomes tertiary if page exists
            else:
                 item_data["secondary"] = meta.get('snippet', '') # Snippet is secondary if no page
            local_section_content["items"].append(item_data)

    else:
         local_section_content = "_No local results found_"
    aggregator_report_data.append({"level": 2, "title": "Local Retrieval Results", "content": local_section_content})


    # Previous Results Section
    if previous_results:
        aggregator_report_data.append({"level": 2, "title": "Previous Results Integrated", "content": previous_results})

    # Follow-Up Conversation Section
    if follow_up_conversation:
        aggregator_report_data.append({"level": 2, "title": "Follow-Up Conversation", "content": follow_up_conversation})


    # --- Write Reports ---

    # File Paths
    final_report_md_path = os.path.join(output_dir, "final_report.md")
    final_report_adoc_path = os.path.join(output_dir, "final_report.adoc")
    aggregator_md_path = os.path.join(output_dir, f"{query_id}_output.md")
    aggregator_adoc_path = os.path.join(output_dir, f"{query_id}_output.adoc")

    # Write Final Reports
    _write_markdown_report(final_report_data, final_report_md_path)
    _write_asciidoc_report(final_report_data, final_report_adoc_path)

    # Write Aggregator Reports
    _write_markdown_report(aggregator_report_data, aggregator_md_path)
    _write_asciidoc_report(aggregator_report_data, aggregator_adoc_path)


    # Return the path to the main Markdown aggregator report (consistent with original behavior)
    return aggregator_md_path
