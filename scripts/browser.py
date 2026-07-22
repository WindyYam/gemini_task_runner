import io
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import time
from PIL import Image
import os
import platform

class Browser:
    def __init__(self, user_data_dir, profile_directory, temp_dir='temp/'):
        self.chrome_options = webdriver.ChromeOptions()

        self.chrome_options.add_argument(f"user-data-dir={user_data_dir}")
        self.chrome_options.add_argument(f"profile-directory={profile_directory}")
        self.chrome_options.add_argument("disable-features=HardwareMediaKeyHandling")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = None
        self.temp_dir = temp_dir

    def start_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            # Execute script to remove webdriver property
            #self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except exceptions.SessionNotCreatedException as e:
            print(f"Session not created. Retrying after killing Chrome: {e}")
            # Kill Chrome processes
            system = platform.system().lower()
            if system == "windows":
                os.system("taskkill /im chrome.exe /f")
            elif system == "darwin":
                os.system("pkill -a 'Google Chrome'")
            elif system == "linux":
                os.system("pkill chrome")
            else:
                print(f"Unsupported operating system: {system}")
            time.sleep(2)  # Give the system time to clean up

            # 🔁 RETRY driver start
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def navigate_to(self, url):
        if not self.driver:
            self.start_driver()

        try:
            # Navigate to the target webpage
            self.driver.get(url)
        except TimeoutException:
            print("Timed out waiting for page to load or element to be found")
        except Exception as e:
            print(f"An error occurred: {e}")
            self.close_driver()
            raise

    def _safe_click(self, element):
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
                element,
            )
            ActionChains(self.driver).move_to_element(element).pause(0.1).perform()
            element.click()
            return True
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False

    def _dismiss_ytmusic_playback_gate(self):
        gate_selectors = [
            "ytmusic-mealbar-promo-renderer button",
            "ytmusic-mealbar-promo-renderer tp-yt-paper-button",
        ]

        for selector in gate_selectors:
            for btn in self.driver.find_elements(By.CSS_SELECTOR, selector):
                text = (btn.text or "").strip().lower()
                if "start playback" in text and self._safe_click(btn):
                    return True

        # Fallback: text-based search for interstitial CTA anywhere on the page.
        xpath_candidates = [
            "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start playback')]",
            "//tp-yt-paper-button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start playback')]",
            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start playback')]/ancestor::button[1]",
        ]
        for xpath in xpath_candidates:
            for btn in self.driver.find_elements(By.XPATH, xpath):
                if self._safe_click(btn):
                    return True

        # Fallback: search in shadow roots for any clickable node containing the text.
        clicked = self.driver.execute_script(
            """
            const target = 'start playback';
            const seen = new Set();
            const queue = [document];

            const getChildren = (root) => {
              const out = [];
              if (!root) return out;
              const nodes = root.querySelectorAll('*');
              for (const n of nodes) {
                out.push(n);
                if (n.shadowRoot) out.push(n.shadowRoot);
              }
              return out;
            };

            while (queue.length) {
              const root = queue.shift();
              if (!root || seen.has(root)) continue;
              seen.add(root);

              for (const node of getChildren(root)) {
                if (!node || seen.has(node)) continue;
                seen.add(node);

                if (node.shadowRoot) queue.push(node.shadowRoot);
                const text = ((node.innerText || node.textContent || '') + ' ' + (node.getAttribute?.('aria-label') || '') + ' ' + (node.getAttribute?.('title') || '')).toLowerCase();
                if (!text.includes(target)) continue;

                const clickable = node.closest?.('button, tp-yt-paper-button, [role=button]') || node;
                try {
                  clickable.scrollIntoView({block: 'center', inline: 'center'});
                  clickable.click();
                  return true;
                } catch (e) {
                  try {
                    clickable.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, composed: true}));
                    return true;
                  } catch (_) {}
                }
              }
            }
            return false;
            """
        )
        if clicked:
            return True

        return False

    def _get_media_state(self):
        return self.driver.execute_script(
            """
            const media = document.querySelector('video, audio');
            if (!media) return null;
            return {
              paused: !!media.paused,
              currentTime: Number(media.currentTime || 0),
              readyState: Number(media.readyState || 0),
              ended: !!media.ended,
            };
            """
        )

    def _is_media_advancing(self, wait_sec=1.0):
        first = self._get_media_state()
        if not first:
            return False
        if first.get("ended"):
            return False
        if not first.get("paused"):
            time.sleep(wait_sec)
            second = self._get_media_state()
            if not second:
                return False
            return second.get("currentTime", 0) > first.get("currentTime", 0)
        return False

    def _ensure_ytmusic_playing(self):
        if self._is_media_advancing(wait_sec=0.8):
            return True

        player_selectors = [
            "tp-yt-paper-icon-button.play-pause-button",
            "ytmusic-player-bar tp-yt-paper-icon-button.play-pause-button",
            "ytmusic-player-bar button[title*='Play']",
            "ytmusic-player-bar button[aria-label*='Play']",
            "ytmusic-player-page tp-yt-paper-icon-button.play-pause-button",
        ]

        for _ in range(4):
            self._dismiss_ytmusic_playback_gate()

            for selector in player_selectors:
                for player_btn in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    title = (player_btn.get_attribute("title") or "").lower()
                    aria_label = (player_btn.get_attribute("aria-label") or "").lower()
                    state_text = f"{title} {aria_label}"
                    if "play" in state_text:
                        self._safe_click(player_btn)
                    elif "pause" in state_text and self._is_media_advancing(wait_sec=0.6):
                        return True

            if self._is_media_advancing(wait_sec=0.8):
                return True

            # Keyboard fallback for dynamic layouts.
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys("k")
            time.sleep(0.25)
            self._dismiss_ytmusic_playback_gate()
            body.send_keys(Keys.SPACE)

            if self._is_media_advancing(wait_sec=0.8):
                return True

        return False

    def play_song(self, song_name):
        if not self.driver:
            self.start_driver()

        try:
            # Open YouTube Music search directly with query params.
            self.driver.get(f"https://music.youtube.com/search?q={quote_plus(song_name)}")

            # Wait for search page to be ready before interacting with controls.
            WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytmusic-section-list-renderer"))
            )

            # Try several candidate selectors and click the first visible/interactable button.
            play_selectors = [
                "ytmusic-responsive-list-item-renderer ytmusic-play-button-renderer button",
                "ytmusic-two-row-item-renderer ytmusic-play-button-renderer button",
                "ytmusic-play-button-renderer button[aria-label*='Play']",
                "ytmusic-play-button-renderer button",
            ]

            clicked = False
            for selector in play_selectors:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for button in buttons:
                    if not button.is_displayed() or not button.is_enabled():
                        continue
                    if self._safe_click(button):
                        clicked = True
                        break
                if clicked:
                    break

            # Fallback: open the first track result directly when no play button can be clicked.
            if not clicked:
                first_track = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ytmusic-responsive-list-item-renderer a[href*='watch?v=']"))
                )
                clicked = self._safe_click(first_track)

            if clicked:
                # Entering the watch page may require an additional playback confirmation.
                clicked = self._ensure_ytmusic_playing()

            if not clicked:
                raise TimeoutException("Could not click play control on YouTube Music search page")

            print(f"Now playing: {song_name}")
            return True

        except TimeoutException:
            print("Timed out waiting for page to load or element to be found")
        except Exception as e:
            print(f"An error occurred: {e}")
            self.close_driver()
            raise
        
        return False
    
    def play_next(self):
        next_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-icon-button.next-button"))
            )
        next_btn.click()
    
    def play_prev(self):
        self.stop_play()
        prev_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-icon-button.previous-button"))
            )
        prev_btn.click()
        time.sleep(0.5)
        prev_btn.click()

    def stop_play(self):
        play_pause_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-icon-button.play-pause-button"))
            )
        play_pause_btn.click()

    def locate_in_map(self):
        self.driver.get("https://www.google.com/maps")
        
        try:
            # Wait for the geolocation button to be clickable
            location_button = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label*="From your device"]'))
            )
            # Click the geolocation button
            location_button.click()
        except Exception as e:
            pass
        
        time.sleep(2)

    def snapshot(self):
        # Take screenshot and save as PNG in memory
        png_data = self.driver.get_screenshot_as_png()
        
        # Convert PNG to JPG using PIL
        image = Image.open(io.BytesIO(png_data))
        rgb_image = image.convert('RGB')  # Convert to RGB mode for JPG
        # Calculate new dimensions
        width = int(rgb_image.size[0] * 80 / 100)
        height = int(rgb_image.size[1] * 80 / 100)
        
        # Resize the image
        resized_image = rgb_image.resize((width, height), Image.Resampling.LANCZOS)

        filename = self.temp_dir + 'browser_snapshot.jpg'
        resized_image.save(filename, 'JPEG', quality=50)
        return 'file:'+filename
    
    def search_map(self, query):
        self.locate_in_map()
        # Wait for the search box to be present
        search_box = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "searchboxinput"))
        )
        
        # Clear any existing text and enter the query
        search_box.clear()
        search_box.send_keys(query)
        
        # Press Enter to search
        search_box.send_keys(Keys.RETURN)
        time.sleep(2)

    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __del__(self):
        self.close_driver()

# Example usage
if __name__ == "__main__":
    # Update these paths to match your system
    player = Browser(
        user_data_dir="C:\\MySource\\gemini_voice_companion\\Chrome_User_Data",
        profile_directory="Default"
    )
    
    try:
        player.start_driver()
        success = player.play_song("chiptune badger lizard")
        if success:
            print("Song started successfully")
            time.sleep(60)  # Wait for 1 minute
        else:
            print("Failed to play song")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        player.close_driver()