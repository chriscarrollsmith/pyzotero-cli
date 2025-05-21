---
description: 
globs: 
alwaysApply: true
---
# Using the `pyzotero-cli` (Entrypoint `zot`) for Read Operations

This document summarizes key commands and techniques for reading and querying your Zotero library using the `zot` command-line interface.

## General Tips

*   **Discovering Options**: Use the `--help` flag with any command or subcommand to see available options and usage details (e.g., `zot items list --help`, `zot items get --help`).
*   **Output Formats**: The `zot` tool can output data in various formats. The `--output <format>` option is crucial for this. Make sure to select a format your text editor supports. Common formats include:
    *   `json` (default for many list/get commands)
    *   `bibtex`
    *   `csljson`
    *   `keys`
    *   `table`
*   **Redirecting Output to Files**: To ensure data integrity and avoid transcription errors, especially when dealing with structured formats like BibTeX or CSL JSON, redirect command output directly to files:
    *   **Overwrite (or create) a file**: Use the `>` operator. This is useful when generating a bibliography file from scratch.
        ```bash
        zot items get <ITEM_KEY> --output bibtex > my_references.bib
        zot items get <KEY1> <KEY2> --output csljson > my_references.json 
        # For CSL JSON, it's best to get all items for a file in one command to ensure a valid JSON array.
        ```
    *   **Append to a file**: Use the `>>` operator. This adds new content to the end of an existing file.
        ```bash
        # Works well for BibTeX:
        zot items get <ANOTHER_ITEM_KEY> --output bibtex >> my_references.bib
        ```
    *   **Note on Appending CSL JSON**: Directly appending (`>>`) output from multiple `zot items get ... --output csljson` commands will result in an invalid JSON file (multiple JSON arrays concatenated). Instead, you can use `jq` to merge the arrays into a single valid JSON array:
        ```bash
        jq -s 'add' references.json <(zot items get ZBZDG3XV --output csljson) > temp.json && mv temp.json references.json
        ```
*   **Citing References in Your Document**: You should review your text editor's documentation for instructions on how to add a bibtex or CSL JSON reference to your document, but typically this involves inserting the CSL JSON id or BibTeX citation key into your document with Pandoc's citation syntax (e.g., `[@20516182/ZBZDG3XV]` or `[@smith_2023]`). Or, to add a pre-formatted reference, you can use `zot items get <ITEM_KEY> --output bib --style <ANY_CSL_STYLE_NAME>`, then copy the output into your document.

## Full-Text Search

The `zot` CLI allows you to perform full-text searches across your Zotero library. This is useful for finding items based on keywords in their titles, abstracts, notes, or even the content of indexed PDF attachments.

*   **Basic Full-Text Search**: Use the `list` subcommand with the `--q` option followed by your search term(s).
    ```bash
    zot items list --q "your search query"
    ```
*   **Searching for Exact Phrases**: Enclose your search query in quotes to find exact phrases.
*   **Outputting Search Results**: You can combine full-text search with output formatting options. For example, to display results in a table:
    ```bash
    zot items list --q "machine learning" --output table
    ```
*   **Scope of Search**: The full-text search typically covers:
    *   Item metadata (titles, author names, abstracts, tags)
    *   Content of notes attached to items
    *   Text content of PDF files and other attachments that Zotero has indexed. (Requires Zotero's PDF indexing to be active).

## Example: Generating Bibliographies with Quarto

[Quarto](https://quarto.org/) is a powerful tool for academic writing that can render to file formats such as .docx and .pdf, [format citations and bibliographies](https://quarto.org/docs/authoring/citations.html), and reproducibly generate charts and tables directly in the document from R or Python code. Here's how to use the `zot` CLI to add citations in Quarto.

1.  **Export Bibliography**: Use `zot items get ... --output bibtex > references.bib` or `zot items get ... --output csljson > references.json` to create your bibliography file.
2.  **Configure Quarto Document**: Point to your bibliography file and citation style in your `.qmd` file's YAML header:
    ```yaml
    ---
    title: "My Document"
    bibliography: references.bib            # or references.json
    csl: https://www.zotero.org/styles/mla  # For rendering with CSL, or
    bibliographystyle: apa                  # For rendering with bibtex
    format: pdf                             # or html, docx, etc.
    ---
    ```
3.  **Cite in Markdown**: Use Pandoc's citation syntax (e.g., `[@citekey]`, `[@smith_2023]`, `[@20516182/MW88FR9I]`).
4.  **Render Document**:
    ```bash
    quarto render my_document.qmd
    ```
