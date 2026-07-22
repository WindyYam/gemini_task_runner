import json
import base64
import io
import requests
from PIL import Image, ImageDraw


BASE_URL = "http://192.168.1.219:11434"
MODEL = "qwen3.5:9b"


def post_json(path, payload):
	url = f"{BASE_URL}{path}"
	r = requests.post(url, json=payload, timeout=120)
	r.raise_for_status()
	return r.json()


def get_json(path):
	url = f"{BASE_URL}{path}"
	r = requests.get(url, timeout=30)
	r.raise_for_status()
	return r.json()


def make_test_image_base64(fmt, size):
	img = Image.new("RGB", (size, size), color=(255, 0, 0))
	buf = io.BytesIO()
	img.save(buf, format=fmt)
	return base64.b64encode(buf.getvalue()).decode("ascii")


def make_meaningful_image_base64(fmt, size):
	img = Image.new("RGB", (size, size), color=(200, 230, 255))
	draw = ImageDraw.Draw(img)

	# Ground
	draw.rectangle([0, int(size * 0.65), size, size], fill=(80, 170, 90))
	# Sun
	r = int(size * 0.1)
	draw.ellipse([size - 3 * r, r, size - r, 3 * r], fill=(255, 220, 80))
	# House body and roof
	draw.rectangle([int(size * 0.25), int(size * 0.45), int(size * 0.55), int(size * 0.72)], fill=(230, 180, 140))
	draw.polygon([
		(int(size * 0.22), int(size * 0.45)),
		(int(size * 0.40), int(size * 0.30)),
		(int(size * 0.58), int(size * 0.45)),
	], fill=(170, 80, 70))
	# Door
	draw.rectangle([int(size * 0.36), int(size * 0.57), int(size * 0.44), int(size * 0.72)], fill=(120, 70, 50))
	# Window
	draw.rectangle([int(size * 0.47), int(size * 0.53), int(size * 0.53), int(size * 0.60)], fill=(180, 230, 255))
	# Label text
	draw.text((int(size * 0.05), int(size * 0.05)), "HELLO", fill=(30, 30, 30))

	buf = io.BytesIO()
	img.save(buf, format=fmt)
	return base64.b64encode(buf.getvalue()).decode("ascii")


def short_http_error(e):
	body = ""
	if e.response is not None and e.response.text:
		body = f" | body: {e.response.text[:500]}"
	return f"HTTP error ({e}){body}"


def test_server_info():
	print("[SERVER INFO]", flush=True)
	try:
		version = get_json("/api/version")
		print("version:", version.get("version"))
		show = post_json("/api/show", {"name": MODEL})
		print("capabilities:", show.get("capabilities"))
	except Exception as e:
		print(f"SERVER INFO FAIL: {e}")


def test_text_generation():
	print("[TEXT TEST]", flush=True)
	payload = {
		"model": MODEL,
		"prompt": "Give me a short greeting in one sentence.",
		"stream": False,
		"think": False,
	}
	try:
		result = post_json("/api/generate", payload)
		output = (result.get("response") or "").strip()
		print(output)
		if output:
			print("TEXT TEST PASS")
		else:
			print("TEXT TEST FAIL: empty response")
	except requests.HTTPError as e:
		print(f"TEXT TEST FAIL: {short_http_error(e)}")
	except Exception as e:
		print(f"TEXT TEST FAIL: {e}")


def run_image_case(endpoint, image_b64, options=None):
	if endpoint == "/api/generate":
		payload = {
			"model": MODEL,
			"prompt": "Describe this image in one short sentence.",
			"images": [image_b64],
			"stream": False,
			"think": False,
		}
		if options:
			payload["options"] = options
		result = post_json(endpoint, payload)
		return (result.get("response") or "").strip()

	payload = {
		"model": MODEL,
		"messages": [
			{
				"role": "user",
				"content": "Describe this image in one short sentence.",
				"images": [image_b64],
			}
		],
		"stream": False,
	}
	if options:
		payload["options"] = options
	result = post_json(endpoint, payload)
	return ((result.get("message") or {}).get("content") or "").strip()


def test_image_input_support():
	print("\n[IMAGE MATRIX TEST]", flush=True)
	base_options = None
	low_resource_options = {
		"num_ctx": 1024,
		"num_batch": 64,
	}
	cases = [
		{"endpoint": "/api/generate", "fmt": "PNG", "size": 8, "options": base_options, "label": "gen png 8 default"},
		{"endpoint": "/api/generate", "fmt": "JPEG", "size": 8, "options": base_options, "label": "gen jpg 8 default"},
		{"endpoint": "/api/generate", "fmt": "PNG", "size": 256, "options": base_options, "label": "gen png 256 default"},
		{"endpoint": "/api/generate", "fmt": "PNG", "size": 8, "options": low_resource_options, "label": "gen png 8 lowres"},
		{"endpoint": "/api/chat", "fmt": "PNG", "size": 8, "options": base_options, "label": "chat png 8 default"},
		{"endpoint": "/api/chat", "fmt": "JPEG", "size": 8, "options": base_options, "label": "chat jpg 8 default"},
		{"endpoint": "/api/chat", "fmt": "PNG", "size": 256, "options": base_options, "label": "chat png 256 default"},
		{"endpoint": "/api/chat", "fmt": "PNG", "size": 8, "options": low_resource_options, "label": "chat png 8 lowres"},
	]

	results = []
	for case in cases:
		if case["size"] >= 256:
			image_b64 = make_meaningful_image_base64(case["fmt"], case["size"])
		else:
			image_b64 = make_test_image_base64(case["fmt"], case["size"])
		try:
			output = run_image_case(case["endpoint"], image_b64, case["options"])
			ok = bool(output)
			msg = output[:120] if output else "empty response"
		except requests.HTTPError as e:
			ok = False
			msg = short_http_error(e)
		except Exception as e:
			ok = False
			msg = str(e)

		results.append((case["label"], ok, msg))
		status = "PASS" if ok else "FAIL"
		print(f"[{status}] {case['label']} -> {msg}")

	passed = sum(1 for _, ok, _ in results if ok)
	print(f"\nIMAGE MATRIX SUMMARY: {passed}/{len(results)} passed")


def main():
	test_server_info()
	print()
	test_text_generation()
	test_image_input_support()


if __name__ == "__main__":
	main()