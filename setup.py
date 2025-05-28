from setuptools import setup, find_packages

setup(
    name='daily_tracker_bot',
    version='0.1.0',
    description='Telegram-бот для трекинга эмоций, питания и генерации отчётов',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author='Жаворонкова Александра',
    author_email='alekkrats@gmail.com',
    url='https://github.com/AleksUon/BOT_TRPP.git',
    packages=find_packages(exclude=['tests', 'docs']),
    python_requires='>=3.7',
    install_requires=[
        'python-telegram-bot>=20.3,<21.0',
        'python-dateutil>=2.8.2',
        'loguru>=0.7.2',
        'python-dotenv>=1.0.1',
        'pysqlite3-binary>=0.5.1; platform_system == "Windows"'
    ],
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'Topic :: Communications :: Chat',
    ],
    entry_points={
        'console_scripts': [
            'daily_tracker_bot=bot.main:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
