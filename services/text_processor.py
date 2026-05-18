"""
Text processing service
Handles text chunking, cleaning, and preprocessing
"""

from typing import List, Dict
import re
from bs4 import BeautifulSoup


class TextProcessor:
    """
    Process and chunk text for vector storage
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        """
        Initialize text processor

        Args:
            chunk_size: Target size for each chunk (characters)
            chunk_overlap: Overlap between chunks (characters)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def clean_html(self, html_content: str) -> str:
        """
        Clean HTML and extract text

        Args:
            html_content: Raw HTML string

        Returns:
            Cleaned text
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text

        Args:
            text: Input text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Strip document/file metadata patterns that appear in scraped Ministry tables
        # e.g. "Published Year:2014" "SizeType: 14.2 MB" "Size: 17.9 MB" "ViewTitle:"
        text = re.sub(r'Published Year\s*:\s*\d{4}', '', text)
        text = re.sub(r'SizeType\s*:\s*[\d.]+ MB', '', text)
        text = re.sub(r'\bSize\s*:\s*[\d.]+ MB\b', '', text)
        text = re.sub(r'\bViewTitle\s*:', '', text)

        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:()\-\'\"।]', '', text)

        # Remove multiple consecutive punctuation
        text = re.sub(r'([.,!?;])\1+', r'\1', text)

        return text.strip()

    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into overlapping chunks

        Args:
            text: Input text to chunk
            metadata: Optional metadata to attach to each chunk

        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text) < 50:  # Skip very short texts
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Calculate end position
            end = start + self.chunk_size

            # If this is not the last chunk, try to break at sentence boundary
            if end < text_length:
                # Look for sentence endings near the target position
                search_start = max(start, end - 100)
                search_end = min(text_length, end + 100)
                search_text = text[search_start:search_end]

                # Find sentence boundaries (., !, ?, ।)
                sentence_endings = [m.end() for m in re.finditer(r'[.!?।]\s+', search_text)]

                if sentence_endings:
                    # Find closest sentence ending to target
                    target_pos = end - search_start
                    closest_ending = min(sentence_endings, key=lambda x: abs(x - target_pos))
                    end = search_start + closest_ending

            # Extract chunk
            chunk_text = text[start:end].strip()

            if len(chunk_text) > 50:  # Only keep meaningful chunks
                chunk_data = {
                    "text": chunk_text,
                    "start_pos": start,
                    "end_pos": end,
                    "chunk_length": len(chunk_text)
                }

                # Add metadata if provided
                if metadata:
                    chunk_data.update(metadata)

                chunks.append(chunk_data)

            # Move start to the next sentence boundary after (end - overlap),
            # so chunks don't begin mid-word or mid-sentence.
            overlap_start = end - self.chunk_overlap
            look_ahead = text[overlap_start: overlap_start + self.chunk_overlap]
            boundary = re.search(r'[.!?।]\s+([A-Z])', look_ahead)
            start = overlap_start + boundary.start(1) if boundary else end

        return chunks

    def process_document(self, content: str, url: str, title: str = None, is_html: bool = True) -> List[Dict]:
        """
        Complete document processing pipeline

        Args:
            content: Raw content (HTML or text)
            url: Source URL
            title: Document title
            is_html: Whether content is HTML

        Returns:
            List of processed chunks with metadata
        """
        # Extract text from HTML if needed
        if is_html:
            text = self.clean_html(content)
        else:
            text = content

        # Clean text
        text = self.clean_text(text)

        # Skip if too short
        if len(text) < 100:
            print(f"Skipping document (too short): {url}")
            return []

        # Prepare metadata
        metadata = {
            "url": url,
            "title": title or "Untitled",
            "source_length": len(content),
            "processed_length": len(text)
        }

        # Chunk text
        chunks = self.chunk_text(text, metadata)

        print(f"Processed {url}: {len(chunks)} chunks")

        return chunks


def get_text_processor(chunk_size: int = 800, chunk_overlap: int = 100) -> TextProcessor:
    """
    Get text processor instance

    Args:
        chunk_size: Target chunk size
        chunk_overlap: Overlap size

    Returns:
        TextProcessor instance
    """
    return TextProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
