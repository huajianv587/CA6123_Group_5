import re


class PIIRedactor:
    def redact(self, text: str) -> str:
        text = re.sub(r"1[3-9]\d{9}", lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], text)
        text = re.sub(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", r"\1***\2", text)
        text = re.sub(r"(20\d{4})\d{4,10}", r"\1****", text)
        text = re.sub(r"([A-Z]{2}\d{3})\d{4,10}", r"\1****", text)
        return text
