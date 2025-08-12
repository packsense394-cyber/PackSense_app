# PackSense - Intelligent Packaging Evaluation Platform

A modern, AI-powered platform for analyzing Amazon product reviews and detecting packaging-related issues. PackSense provides intelligent insights into product packaging quality through advanced NLP analysis and visual defect detection.

## 🚀 Features

- **Modern UI/UX**: Beautiful, responsive design with glassmorphism effects
- **Product Overview**: Stunning landing page with key metrics and insights
- **Advanced Analysis**: Detailed review analysis with co-occurrence networks
- **Defect Detection**: Visual overlay system for identifying packaging defects
- **Real-time Processing**: Live scraping and analysis of Amazon reviews
- **Smart Filtering**: Intelligent keyword-based review filtering
- **Export Capabilities**: Download analysis results and images

## 📁 Project Structure

```
PackSense/
├── app.py                 # Main Flask application
├── config.py              # Configuration and constants
├── scraper.py             # Web scraping and image processing
├── nlp_utils.py           # NLP and text analysis functions
├── run.py                 # Application launcher script
├── templates/             # HTML templates
│   ├── index.html         # Home page
│   ├── product_overview.html  # Product overview page
│   └── results_enhanced.html  # Detailed analysis page
├── static/                # Static assets and data
└── README.md              # This file
```

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd PackSense
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Chrome WebDriver** (for web scraping):
   ```bash
   # On macOS with Homebrew
   brew install chromedriver
   
   # Or download from: https://chromedriver.chromium.org/
   ```

## 🚀 Quick Start

1. **Run the application**:
   ```bash
   python run.py
   ```

2. **Open your browser** and navigate to:
   ```
   http://127.0.0.1:5008
   ```

3. **Enter Amazon credentials** and a product review URL to start analysis

## 📋 Requirements

- Python 3.8+
- Chrome browser
- ChromeDriver
- Internet connection for Amazon scraping

### Python Dependencies

```
flask
selenium
pandas
numpy
scikit-learn
mlxtend
nltk
pillow
requests
apscheduler
xlsxwriter
```

## 🎨 UI/UX Features

### Product Overview Page
- **Modern gradient background** with animated elements
- **Interactive data cards** with progress indicators
- **Feature showcase** with 3D-style icons
- **Floating action button** for navigation

### Analysis Page
- **Enhanced metrics cards** with hover effects
- **Tabbed interface** for organized content
- **Modern form controls** with gradient styling
- **Responsive design** for all screen sizes

### Visual Design Elements
- **Glassmorphism effects** with backdrop blur
- **Smooth animations** and transitions
- **Professional color scheme** (blue gradients)
- **Modern typography** (Inter font family)

## 🔧 Configuration

### Environment Variables
- `FLASK_ENV`: Set to `development` for debug mode
- `CHROME_DRIVER_PATH`: Path to ChromeDriver (optional)

### Customization
Edit `config.py` to modify:
- Component and condition keywords
- NLTK settings
- Default parameters

## 📊 Analysis Features

### Review Processing
- **Sentiment Analysis**: Positive, negative, neutral classification
- **Keyword Extraction**: Automatic packaging-related term detection
- **Co-occurrence Analysis**: Relationship mapping between components and conditions
- **Defect Detection**: Visual overlay system for product images

### Export Options
- **Excel Reports**: Comprehensive analysis data
- **Image Downloads**: All review images in ZIP format
- **Packaging Library**: Updated terminology database

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   lsof -ti:5008 | xargs kill -9
   ```

2. **ChromeDriver not found**:
   - Download ChromeDriver from https://chromedriver.chromium.org/
   - Add to PATH or specify path in environment

3. **NLTK data missing**:
   ```python
   import nltk
   nltk.download('wordnet')
   nltk.download('vader_lexicon')
   ```

4. **Amazon login issues**:
   - Ensure credentials are correct
   - Check for CAPTCHA requirements
   - Verify account is not locked

### Debug Mode
Run with debug enabled:
```bash
export FLASK_ENV=development
python run.py
```

## 🔒 Security Notes

- **Credentials**: Amazon credentials are processed securely
- **Data Storage**: All data is stored locally
- **No External APIs**: All processing is done locally
- **Session Management**: Flask sessions for user data

## 📈 Performance

- **Optimized Scraping**: Efficient pagination and deduplication
- **Caching**: Local storage of processed data
- **Background Processing**: Non-blocking analysis operations
- **Memory Management**: Efficient data structures and cleanup

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the code documentation
3. Create an issue on GitHub

## 🔄 Updates

### Recent Changes
- **Modular Architecture**: Separated code into logical modules
- **Enhanced UI**: Modern design with glassmorphism effects
- **Improved Navigation**: Better user flow and experience
- **Code Organization**: Cleaner, more maintainable structure

### Future Enhancements
- Real-time notifications
- Advanced analytics dashboard
- Multi-language support
- API endpoints for external integration 