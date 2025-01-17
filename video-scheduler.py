# %% [markdown]
# # Telegram Bot to YouTube Shorts Uploader with Video Overlay
# This notebook:
# 1. Connects to a Telegram bot
# 2. Downloads the latest media
# 3. Applies video overlay processing
# 4. Converts it to a YouTube Short
# 5. Uploads it to YouTube

# %%
import os
import json
import time
import random
import numpy as np
from datetime import datetime
import requests
from PIL import Image
import moviepy.editor as mp
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from apscheduler.schedulers.background import BackgroundScheduler
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import google.auth.transport.requests
from googleapiclient.http import MediaFileUpload
import matplotlib.pyplot as plt
import schedule
from dotenv import load_dotenv
import logging
import shutil

# %% [markdown]
# ## Configuration

# %%

logging.basicConfig(level=logging.INFO)

load_dotenv()
CONFIG = {
    'telegram_token': os.getenv("TELEGRAM_TOKEN"),
    'chat_id': os.getenv("TELEGRAM_CHAT_ID"),
    'base_folder': 'data',
    'images_folder': 'data/input/images',
    'videos_folder': 'data/input/videos',
    'output_folder': '/tmp',
    'last_update_id': 0,

    'client_secrets_file': 'client_secrets.json', 
    'video_file': 'data/output/overlay_Unbenannt.mp4', 
    'video_description': '', 
    'video_tags': ['#memes', '#funny'],
    'privacy_status': 'public'
}

# Read Google credentials from environment variables
google_credentials = {
    "installed": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": ["http://localhost"]
    }
}

# Write credentials to a temporary file if needed
with open("client_secrets.json", "w") as f:
    json.dump(google_credentials, f)

total, used, free = shutil.disk_usage("/")
print("Total: %d GB" % (total // (2**30)))
print("Used: %d GB" % (used // (2**30)))
print("Free: %d GB" % (free // (2**30)))

# Create all necessary folders
for folder in [ 'videos_folder', 'images_folder', 'output_folder']:
    os.makedirs(CONFIG[folder], exist_ok=True)

# Function to validate paths
def validate_config():
    issues = []
    if not os.path.exists(CONFIG['client_secrets_file']):
        issues.append(f"Client secrets file not found at: {CONFIG['client_secrets_file']}")
    if not os.path.exists(CONFIG['videos_folder']):
        issues.append(f"Background Video files not found at: {CONFIG['videos_folder']}")
    
    if issues:
        print("⚠️ Configuration issues found:")
        for issue in issues:
            print(f"- {issue}")
        return False
    print("✅ Configuration validated successfully!")
    return True

validate_config()

# %% [markdown]
# ## YouTube API Authentication

def authenticate_youtube():
    """Authenticate using a saved refresh token and return API client"""
    api_name = "youtube"
    api_version = "v3"

    try:
        credentials = google.oauth2.credentials.Credentials(
            None,  # No access token initially
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            token_uri="https://oauth2.googleapis.com/token"
        )

        # Try to refresh the token
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        # If refresh succeeded, save the new refresh token
        if credentials.refresh_token:
            # Save the new refresh token to environment variable or secure storage
            os.environ["GOOGLE_REFRESH_TOKEN"] = credentials.refresh_token
            print("✅ Token refreshed successfully!")

        youtube = googleapiclient.discovery.build(
            api_name, 
            api_version, 
            credentials=credentials
        )
        message = "✅ Authentication successful!"
        print(message)
        send_message(CONFIG['chat_id'], message)
        return youtube
    
    except google.auth.exceptions.RefreshError as e:
        message = f"❌ Token refresh failed: {str(e)}"
        print(message)
        send_message(CONFIG['chat_id'], message)
        # Here you could implement logic to get a new token
        get_new_token()
        return None
    
    except Exception as e:
        message = f"❌ Authentication failed: {str(e)}"
        print(message)
        send_message(CONFIG['chat_id'], message)
        return None

def get_new_token():
    """Get a new token when refresh fails"""
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        CONFIG['client_secrets_file'],
        scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.force-ssl"
        ]
    )
    
    # This will require manual intervention - opening a browser
    credentials = flow.run_local_server(port=8080)
    
    # Save the new refresh token
    if credentials.refresh_token:
        os.environ["GOOGLE_REFRESH_TOKEN"] = credentials.refresh_token
        print("✅ New refresh token obtained!")
        
        # You might want to save this to a secure location
        # For example, update your .env file
        with open('.env', 'r') as file:
            lines = file.readlines()
        
        with open('.env', 'w') as file:
            for line in lines:
                if line.startswith('GOOGLE_REFRESH_TOKEN='):
                    file.write(f'GOOGLE_REFRESH_TOKEN={credentials.refresh_token}\n')
                else:
                    file.write(line)

def get_random_title():
    """Read titles from a file and return a random one"""
    try:
        with open('generic_video_titles.txt', 'r') as file:
            # Read all lines and remove empty lines
            titles = [line.strip() for line in file.readlines() if line.strip()]
            
        if not titles:
            return "Meme of the day"  # Fallback title if file is empty
            
        # Select random title and add hashtags
        random_title = random.choice(titles)
        return f"{random_title} #shorts #memes #funny"
    except FileNotFoundError:
        print("Titles file not found, using default title")
        return "Meme of the day #shorts #memes #funny"
    except Exception as e:
        print(f"Error reading titles: {e}")
        return "Meme of the day #shorts #memes #funny"

# %% [markdown]
# ## Preview Functions
# These functions will help us visualize our selection before creating the final video

# %%
def preview_selection(video_path, image_path):
    """Preview the selected video (first frame) and image"""
    # Load video and get first frame
    video = VideoFileClip(video_path)
    first_frame = video.get_frame(0)
    video.close()
    
    # Load image
    img = Image.open(image_path)
    
    # Create subplot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
    
    # Show first frame of video
    ax1.imshow(first_frame)
    ax1.set_title('First Frame of Video')
    ax1.axis('off')
    
    # Show image
    ax2.imshow(img)
    ax2.set_title('Selected Image')
    ax2.axis('off')
    
    plt.tight_layout()
    plt.show()


# %% [markdown]
# ## Video Overlay Generator Class

# %%
class VideoOverlayGenerator:
    def __init__(self, videos_folder, images_folder, output_folder):
        self.videos_folder = videos_folder
        self.images_folder = images_folder
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)

        # Get all video and image files
        self.video_files = [f for f in os.listdir(videos_folder)
                          if f.endswith(('.mp4', '.mov', '.avi'))]
        self.image_files = [f for f in os.listdir(images_folder)
                          if f.endswith(('.jpg', '.png', '.jpeg'))]

    def get_random_background_video(self):
        """Get random video file from the specified folders"""
        video_files = [f for f in os.listdir(self.videos_folder) 
                    if f.endswith(('.mp4', '.mov', '.avi'))]
        
        if not video_files:
            raise ValueError("No video files found in the specified folders")
            
        return random.choice(video_files)

    def resize_image_for_video(self, image, video_width, video_height):
        """Resize image to fit in the bottom half of the video while maintaining aspect ratio"""
        target_height = int(video_height * 0.65)  # Use 75% of video height
        target_width = video_width
        
        # Calculate aspect ratio
        img_aspect = image.size[0] / image.size[1]
        target_aspect = target_width / target_height
        
        if img_aspect > target_aspect:
            # Image is wider than target area
            new_width = target_width
            new_height = int(target_width / img_aspect)
        else:
            # Image is taller than target area
            new_height = target_height
            new_width = int(target_height * img_aspect)
            
        return image.resize((new_width, new_height), Image.LANCZOS)

    def create_overlay_video(self):
        """Create a video with an image overlay"""
        # Get random files
        video_file = self.get_random_background_video()

        if self.image_files:
            image_file = self.image_files[0]
        else:
            print("No image files found.")

        
        # Get full paths
        video_path = os.path.join(self.videos_folder, video_file)
        image_path = os.path.join(self.images_folder, image_file)
        
        # Preview selection
        print("Selected files:")
        print(f"Video: {video_file}")
        print(f"Image: {image_file}")
        preview_selection(video_path, image_path)
        
        # Load video and get dimensions
        video = VideoFileClip(video_path)
        video_width, video_height = video.size
        
        # Load and resize image
        img = Image.open(image_path)
        resized_img = self.resize_image_for_video(img, video_width, video_height)
        
        # Convert PIL image to ImageClip
        image_clip = ImageClip(np.array(resized_img))
        
        # Position image at the top center of video with 10% margin from top
        top_margin = int(video_height * 0.1)  # 10% margin from top
        x_pos = (video_width - resized_img.width) // 2
        y_pos = top_margin  # Simply place it at the top margin position
        
        # Set duration of image to match video
        image_clip = image_clip.set_duration(video.duration)
        image_clip = image_clip.set_position((x_pos, y_pos))
        
        # Composite video with image overlay
        final_video = CompositeVideoClip([video, image_clip])
        
        # Generate output filename
        output_filename = f"overlay_{os.path.splitext(video_file)[0]}.mp4"
        output_path = os.path.join(self.output_folder, output_filename)
        
        # Write final video
        print("\nCreating video...")
        try:
            final_video.write_videofile(output_path, 
                                codec='libx264',
                                audio_codec='aac')
        except Exception as e:
            print(f"Error writing video: {e}")
        
        # Close clips to free resources
        video.close()
        final_video.close()
        
        return output_path

# %% [markdown]
# ## Telegram Functions

# %%
def get_telegram_updates():
    """Get updates from Telegram bot"""
    url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/getUpdates"
    params = {
        'offset': CONFIG['last_update_id'] + 1,
        'timeout': 30
    }
    
    try:
        response = requests.get(url, params=params)
        print(response.json())
        return response.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return None

def download_file(file_id, is_video=False):
    """Download a file from Telegram"""
    try:
        # Get file path
        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/getFile"
        response = requests.get(url, params={'file_id': file_id})
        file_path = response.json()['result']['file_path']
        
        # Download file
        download_url = f"https://api.telegram.org/file/bot{CONFIG['telegram_token']}/{file_path}"
        response = requests.get(download_url)
        
        # Generate filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = os.path.splitext(file_path)[1]
        filename = f"{timestamp}{extension}"
        
        # Determine the appropriate folder based on file type
        target_folder = CONFIG['videos_folder'] if is_video else CONFIG['images_folder']
        filepath = os.path.join(target_folder, filename)
        print("downloaded image to"+str(filepath))
        # Save file
        with open(filepath, 'wb') as f:
            f.write(response.content)
            
        return filepath
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

# %% [markdown]
# ## Video Upload Function

# %%
def upload_youtube_short(youtube, video_file, title, description="", tags=None, sender_chat_id=None):
    """Upload a video as a YouTube Short"""
    if not youtube:
        print("❌ YouTube API client not initialized")
        return None
    
    # Prepare the video metadata
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "22"  # People & Blogs category
        },
        "status": {
            "privacyStatus": "private",  # Start as private
            "selfDeclaredMadeForKids": False
        }
    }
    
    # Prepare the video file upload
    media = MediaFileUpload(
        video_file,
        mimetype="video/mp4",
        resumable=True
    )
    
    try:
        # Call the API to insert the video
        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        # Execute the upload with progress tracking
        response = None
        start_upload_message = "📤 Starting upload..."
        print(start_upload_message)
        if sender_chat_id:  # Only send to the original sender
            send_message(sender_chat_id, start_upload_message)
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"Upload progress: {progress}%")
        
        video_id = response['id']
        message = f"🎉 Upload Successful! Video URL: https://www.youtube.com/watch?v={video_id}"
        print(message)
        if sender_chat_id:  # Only send to the original sender
            send_message(sender_chat_id, message)

        # Delete the video after successful upload
        if CONFIG['video_file'] and os.path.exists(CONFIG['video_file']):
            os.remove(CONFIG['video_file'])
            print(f"Deleted generate video file: {CONFIG['video_file']}")
        
        # Update video with vertical metadata for Shorts
        youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {
                    "shortForm": True,  # Mark as Short
                    "privacyStatus": CONFIG['privacy_status']
                }
            }
        ).execute()

    except googleapiclient.errors.HttpError as e:
        error_message = f"❌ An HTTP error occurred: {e.resp.status} - {e.content}"
        print(error_message)
        send_message(CONFIG['chat_id'], error_message)
        return None
    except Exception as e:
        error_message = f"❌ An error occurred: {str(e)}"
        print(error_message)
        send_message(CONFIG['chat_id'], error_message)
        return None


# %% [markdown]
# ## Send status to Bot

# %%
def send_message(chat_id, message):
    """Send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Message sent to Telegram: {message}")
        else:
            print(f"⚠️ Failed to send message. Response: {response.text}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")
    


# %% [markdown]
# ## Main Processing Function

# %%
def process_new_media():
    """Main function to process new media from Telegram"""
    print("Checking for new media...")

    # Get updates from Telegram
    updates = get_telegram_updates()
    if not updates or not updates.get('ok') or not updates.get('result'):
        print("No new updates or error getting updates")
        return

    # Process only the latest update
    last_update = updates['result'][-1]
    CONFIG['last_update_id'] = last_update['update_id']

    # Get the chat ID of the user who sent the message
    if 'message' not in last_update or 'chat' not in last_update['message']:
        print("No valid message in update")
        return
        
    sender_chat_id = last_update['message']['chat']['id']

    # Check if update contains a message with photo or video
    message = last_update.get('message', {})
    downloaded_path = None

    if message.get('photo'):
        # Get the largest photo (last in the array)
        file_id = message['photo'][-1]['file_id']
        downloaded_path = download_file(file_id, is_video=False)
    elif message.get('video'):
        file_id = message['video']['file_id']
        downloaded_path = download_file(file_id, is_video=True)

    if downloaded_path:
        print(f"Downloaded new media: {downloaded_path}")
        try:
            generator = VideoOverlayGenerator(
                CONFIG['videos_folder'],
                CONFIG['images_folder'],
                CONFIG['output_folder']
            )
            overlay_path = generator.create_overlay_video()
            print(f"Created overlay video: {overlay_path}")

            # Delete the image after overlay creation
            if downloaded_path and os.path.exists(downloaded_path):
                os.remove(downloaded_path)
                print(f"Deleted image file: {downloaded_path}")

            if validate_config():
                youtube = authenticate_youtube()
                if youtube:
                    # Pass the sender's chat_id to upload_youtube_short
                    upload_youtube_short(
                        youtube,
                        overlay_path,
                        get_random_title(),
                        CONFIG['video_description'],
                        CONFIG['video_tags'],
                        sender_chat_id  # Add this parameter
                    )

        except Exception as e:
            print(f"Error processing media: {e}")

# %% [markdown]
# ## Schedule the Job

# %%
def task():
    print("Running scheduled task!")
    
    process_new_media()

schedule.every(1).minutes.do(task)

# %% [markdown]
# ## Run the Bot
# Execute this cell to start the bot

# %%
if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)

# %%
