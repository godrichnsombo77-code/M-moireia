import requests


class QwenClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def analyze_image_base64(self, image_b64: str, prompt: str) -> str:
        if not self.base_url:
            return "Qwen server non configure."

        url = f"{self.base_url}/qwen/analyze"
        payload = {
            "prompt": prompt,
            "image_base64": image_b64,
            "max_new_tokens": 180,
            "temperature": 0.2,
        }
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        return data.get("answer", "")

