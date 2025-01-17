# YouTube Short Video Generator

This project generates YouTube short videos from images posted in a Telegram bot channel. The app can be installed and run locally in a Docker container.

## Prerequisites

- Docker application installed and running.

## Installation

1. Clone the repository to your local machine:

2. Build the Docker image:
    ```sh
    docker build -t short-gen-app .
    ```

3. Create an `.env` file with the necessary environment variables. Example:
    ```sh
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    TELEGRAM_CHANNEL_ID=your_telegram_channel_id
    YOUTUBE_API_KEY=your_youtube_api_key
    ```

4. Run the Docker container:
    ```sh
    docker run --env-file .env -d short-gen-app
    ```

## Usage

1. Post images to your Telegram bot channel.
2. The app will automatically generate YouTube short videos from the images and upload them to your YouTube account.

## Contributing

If you'd like to contribute to the project, please fork the repository and use a feature branch. Pull requests are warmly welcome.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

