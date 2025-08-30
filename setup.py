from setuptools import setup, find_packages

setup(
    name="cake-order-bot",
    version="1.0.0",
    description="Telegram бот для заказа тортов",
    packages=find_packages(),
    install_requires=[
        "aiogram==3.5.0",
        "python-dotenv==1.0.1",
        "aiohttp==3.9.1",
    ],
    python_requires=">=3.8",
)
