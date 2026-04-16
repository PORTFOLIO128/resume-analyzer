import asyncio
import io
from app.services.analyzer import ResumeAnalyzer

async def main():
    try:
        analyzer = ResumeAnalyzer()
        # Create a valid minimal PDF in-memory (starts with %PDF)
        # Using a tiny fake PDF byte sequence so it passes the %PDF check
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        print('Testing analyze()...')
        res = await analyzer.analyze(pdf_bytes)
        print('Success:', res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
