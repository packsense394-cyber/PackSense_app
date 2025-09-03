# PackSense 🚀

**Intelligent Packaging Evaluation & Optimization Platform**

PackSense is an advanced web application that analyzes Amazon product reviews to extract packaging-related insights, identify defects, and provide comprehensive co-occurrence network visualizations. Built with Python Flask and featuring interactive D3.js visualizations.

## ✨ Features

### 🔍 **Intelligent Review Analysis**
- **Recursive Review Extraction**: Automatically extracts comprehensive review data from Amazon product pages
- **Packaging-Specific Analysis**: Focuses on packaging-related reviews and feedback
- **Sentiment Analysis**: Advanced NLP-powered sentiment classification using NLTK and VADER
- **Keyword Extraction**: Identifies packaging components and conditions from review text

### 📊 **Interactive Visualizations**
- **Co-occurrence Network**: Interactive D3.js network showing relationships between packaging terms
- **Enhanced Filtering**: Real-time filtering by connection strength and node connections
- **Defect Mapping**: Visual overlay of packaging defects on product images
- **Review Analytics**: Comprehensive charts and statistics

### 🎯 **Advanced Analytics**
- **TF-IDF Analysis**: Term frequency analysis for packaging keywords
- **Association Rules**: Market basket analysis for packaging co-occurrences
- **Neo4j Integration**: Graph database support for complex relationship analysis
- **Recursive Analysis**: Multi-level review extraction strategy

## 🛠️ Technology Stack

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Visualization**: D3.js, Plotly
- **Database**: Neo4j (optional)
- **ML/NLP**: scikit-learn, NLTK, TextBlob, MLxtend
- **Web Scraping**: Selenium, BeautifulSoup
- **Data Processing**: Pandas, NumPy

## 📦 Installation

### Prerequisites
- Python 3.8+
- Chrome/Chromium browser (for web scraping)
- Neo4j (optional, for graph database features)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/PackSense.git
   cd PackSense
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download NLTK data**
   ```bash
   python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4'); nltk.download('vader_lexicon')"
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

## 🚀 Usage

### Demo Mode (Recommended)
1. Navigate to `/demo` for a full demonstration
2. Explore pre-loaded sample data without scraping
3. Test all features including co-occurrence networks and defect analysis
4. No Amazon credentials required

### Live Analysis
1. Navigate to the home page
2. Enter an Amazon product reviews URL
3. Provide your Amazon credentials (for authenticated scraping)
4. Choose analysis type:
   - **Enhanced Analysis**: Comprehensive packaging review analysis
   - **Recursive Analysis**: Multi-level review extraction strategy

**Note**: Live scraping is currently paused due to Amazon's automated activity detection. Use Demo Mode to explore all features.

### Advanced Features

#### Co-occurrence Network
- Click on any node to see related reviews
- Use filter controls to adjust visualization
- Drag nodes to explore relationships
- Hover for detailed information

#### Defect Analysis
- View packaging defects overlaid on product images
- Analyze defect patterns and frequencies
- Export defect reports

#### Neo4j Integration
- Connect to Neo4j database for advanced graph analysis
- Store and query co-occurrence relationships
- Perform complex graph queries

## ⚙️ Configuration

### Environment Variables
```bash
# Neo4j Configuration (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
```

### Customization
- **Packaging Components**: Edit `config.py` to modify component lists
- **Conditions**: Update condition keywords in `config.py`
- **Visualization**: Customize D3.js parameters in templates

## 📁 Project Structure

```
PackSense/
├── app.py                 # Main Flask application
├── config.py             # Configuration and constants
├── nlp_utils.py          # NLP and text processing utilities
├── scraper.py            # Web scraping functionality
├── neo4j_utils.py        # Neo4j database utilities
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates
│   ├── index.html
│   ├── results_enhanced.html
│   ├── recursive_analyze.html
│   └── ...
├── static/               # Static assets and data
└── logs/                 # Application logs
```

## 🔧 API Endpoints

### Main Routes
- `GET /` - Home page
- `GET /demo` - Demo mode with sample data
- `GET /demo-product` - Demo product information page
- `POST /analyze` - Start enhanced analysis
- `POST /recursive_analyze` - Start recursive analysis
- `GET /results/<product_folder>` - View analysis results
- `GET /neo4j/<product_folder>` - Neo4j graph visualization
- `POST /chat` - AI chat assistant for review analysis

### Data Endpoints
- `GET /api/cooccurrence/<product_folder>` - Co-occurrence data
- `GET /api/reviews/<product_folder>` - Review data
- `GET /api/defects/<product_folder>` - Defect analysis

## 🎨 Features in Detail

### Recursive Review Extraction
- **Multi-level Strategy**: Extracts reviews from multiple angles
- **Keyword-based Filtering**: Focuses on packaging-related content
- **Comprehensive Coverage**: Captures both positive and negative feedback

### Interactive Network Visualization
- **D3.js Powered**: Smooth, interactive network graphs
- **Real-time Filtering**: Adjust visibility based on connection strength
- **Node Interaction**: Click, hover, and drag functionality
- **Responsive Design**: Adapts to different screen sizes

### Advanced NLP Processing
- **Sentiment Analysis**: VADER sentiment scoring
- **Keyword Extraction**: TF-IDF based term extraction
- **Association Rules**: Market basket analysis for co-occurrences
- **Text Summarization**: Automatic review summarization

## 🚨 Important Notes

### Current Status
- **Live Scraping Paused**: Amazon has detected automated activity
- **Demo Mode Available**: Full functionality with sample data at `/demo`
- **Professional Error Handling**: Clear messaging about service status

### Amazon Scraping (When Available)
- **Authentication Required**: You need valid Amazon credentials
- **Rate Limiting**: Built-in delays to respect Amazon's terms
- **Headless Mode**: Option to run without browser window
- **CAPTCHA Handling**: Automatic CAPTCHA detection and handling

### Data Privacy
- **Local Storage**: All data stored locally
- **No Data Sharing**: Your Amazon credentials are not stored
- **Secure Processing**: Credentials used only for scraping

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **NLTK**: Natural language processing toolkit
- **D3.js**: Data-driven document manipulation
- **Selenium**: Web browser automation
- **Flask**: Web framework for Python
- **Neo4j**: Graph database platform

## 📞 Support

For support, email your-email@example.com or create an issue in the GitHub repository.

## 🔮 Roadmap

- [ ] **Machine Learning Models**: Advanced packaging defect prediction
- [ ] **Real-time Monitoring**: Live Amazon review monitoring
- [ ] **API Integration**: RESTful API for third-party integrations
- [ ] **Mobile App**: React Native mobile application
- [ ] **Cloud Deployment**: AWS/Azure deployment options
- [ ] **Multi-language Support**: Support for multiple languages
- [ ] **Advanced Analytics**: Time-series analysis and trends

---

**PackSense** - Making packaging analysis intelligent and accessible! 🎯
