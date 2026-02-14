#!/usr/bin/env python3
"""
Script to verify generated resume PDFs.

Usage:
    python scripts/verify_resumes.py
    python scripts/verify_resumes.py output/resumes/Resume_4320909487.pdf
"""

import subprocess
import sys
from pathlib import Path


def check_pdf_valid(pdf_path: Path) -> bool:
    """Check if PDF is valid and can be opened."""
    try:
        subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"❌ {pdf_path.name}: Invalid or corrupted PDF")
        return False
    except FileNotFoundError:
        print("⚠️  pdfinfo not found. Install poppler-utils: brew install poppler")
        return None


def extract_text(pdf_path: Path) -> str:
    """Extract text from PDF for verification."""
    try:
        result = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, check=True)
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def verify_resume_content(text: str, pdf_name: str) -> dict:
    """Verify resume has expected sections and content."""
    issues = []
    warnings = []

    # Check for required sections
    required_sections = ["Experience", "Education", "Technical Skills", "Projects"]

    for section in required_sections:
        if section not in text:
            issues.append(f"Missing section: {section}")

    # Check for contact info
    if "@" not in text or "gmail.com" not in text:
        warnings.append("Email might be missing")

    # Check for dates in experience
    if "2024" not in text and "2023" not in text:
        warnings.append("Experience dates might be missing")

    # Check for escaped characters that shouldn't be visible
    if "\\%" in text:
        issues.append("Found literal \\% in text (escaping issue)")

    if "\\_" in text:
        issues.append("Found literal \\_ in text (escaping issue)")

    # Check if contact info is reasonable length (not wrapped)
    lines = text.split("\n")
    if len(lines) > 2:
        # Contact section should be in first few lines
        header_lines = lines[:3]
        if any(len(line) < 20 and "|" in line for line in header_lines):
            warnings.append("Contact line might be wrapped (too short)")

    # Check for hallucination indicators
    suspicious_words = ["lorem ipsum", "example.com", "YYYY", "XX", "TODO"]
    for word in suspicious_words:
        if word.lower() in text.lower():
            issues.append(f"Found placeholder/template text: {word}")

    return {"issues": issues, "warnings": warnings, "valid": len(issues) == 0}


def verify_pdf(pdf_path: Path) -> dict:
    """Verify a single PDF resume."""
    result = {"file": pdf_path.name, "exists": pdf_path.exists(), "valid_pdf": False, "content_check": None}

    if not result["exists"]:
        print(f"❌ {pdf_path.name}: File not found")
        return result

    # Check PDF validity
    is_valid = check_pdf_valid(pdf_path)
    if is_valid is None:
        # pdfinfo not available, skip validation
        result["valid_pdf"] = "unknown"
    else:
        result["valid_pdf"] = is_valid
        if not is_valid:
            return result

    # Extract and verify content
    text = extract_text(pdf_path)
    if text:
        content_check = verify_resume_content(text, pdf_path.name)
        result["content_check"] = content_check

        # Print results
        if content_check["valid"] and not content_check["warnings"]:
            print(f"✅ {pdf_path.name}: All checks passed")
        else:
            print(f"⚠️  {pdf_path.name}: Has issues")
            for issue in content_check["issues"]:
                print(f"   ❌ {issue}")
            for warning in content_check["warnings"]:
                print(f"   ⚠️  {warning}")
    else:
        print(f"⚠️  {pdf_path.name}: Could not extract text (pdftotext not available)")

    return result


def main():
    """Main verification function."""
    if len(sys.argv) > 1:
        # Verify specific PDF(s)
        pdf_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Verify all PDFs in output/resumes/
        resumes_dir = Path("output/resumes")
        if not resumes_dir.exists():
            print(f"❌ Directory not found: {resumes_dir}")
            return 1

        pdf_paths = list(resumes_dir.glob("Resume_*.pdf"))
        if not pdf_paths:
            print(f"⚠️  No Resume_*.pdf files found in {resumes_dir}")
            return 0

    print(f"Verifying {len(pdf_paths)} resume(s)...\n")

    results = []
    for pdf_path in sorted(pdf_paths):
        result = verify_pdf(pdf_path)
        results.append(result)
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = len(results)
    valid_pdfs = sum(1 for r in results if r["valid_pdf"] is True)
    passed_content = sum(1 for r in results if r["content_check"] and r["content_check"]["valid"])

    print(f"Total PDFs: {total}")
    print(f"Valid PDFs: {valid_pdfs}/{total}")
    print(f"Content checks passed: {passed_content}/{total}")

    # List problematic files
    problematic = [r for r in results if not r["valid_pdf"] or (r["content_check"] and not r["content_check"]["valid"])]

    if problematic:
        print(f"\n⚠️  Problematic files ({len(problematic)}):")
        for r in problematic:
            print(f"   - {r['file']}")
        return 1
    else:
        print("\n✅ All resumes verified successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
