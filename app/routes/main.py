from flask import Blueprint, render_template, request, jsonify, current_app, url_for, Response
from flask_login import current_user
from app.models.resource import Resource
from app.models.discussion import Discussion
import google.generativeai as genai
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    # Get recent resources
    recent_resources = current_app.db.resources.find().sort('created_at', -1).limit(6)
    
    # Get recent discussions
    recent_discussions = current_app.db.discussions.find().sort('created_at', -1).limit(6)
    
    return render_template('main/index.html', 
                         recent_resources=recent_resources,
                         recent_discussions=recent_discussions)

@bp.route('/about')
def about():
    return render_template('main/about.html')

@bp.route('/contact')
def contact():
    return render_template('main/contact.html')

@bp.route('/faq')
def faq():
    return render_template('main/faq.html')

@bp.route('/terms')
def terms():
    return render_template('main/terms.html')

@bp.route('/privacy')
def privacy():
    return render_template('main/privacy.html')

@bp.route('/search')
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', 'all')
    
    results = []
    
    if category in ['all', 'resources']:
        # Search resources
        for resource_data in current_app.db.resources.find({
            '$text': {'$search': query}
        }).sort('views', -1):
            results.append({
                'type': 'resource',
                'data': Resource(resource_data)
            })
    
    if category in ['all', 'discussions']:
        # Search discussions
        for discussion_data in current_app.db.discussions.find({
            '$text': {'$search': query},
            'status': 'active'
        }).sort('created_at', -1):
            results.append({
                'type': 'discussion',
                'data': Discussion(discussion_data)
            })
    
    return render_template('main/search.html', results=results, query=query, category=category)

@bp.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    category = request.args.get('category', 'all')
    
    results = []
    
    if category in ['all', 'resources']:
        # Search resources
        for resource_data in current_app.db.resources.find({
            '$text': {'$search': query}
        }).sort('views', -1).limit(10):
            resource = Resource(resource_data)
            results.append({
                'type': 'resource',
                'id': resource.id,
                'title': resource.title,
                'description': resource.description,
                'views': resource.views,
                'url': url_for('resources.view_resource', resource_id=resource.id)
            })
    
    if category in ['all', 'discussions']:
        # Search discussions
        for discussion_data in current_app.db.discussions.find({
            '$text': {'$search': query},
            'status': 'active'
        }).sort('created_at', -1).limit(10):
            discussion = Discussion(discussion_data)
            results.append({
                'type': 'discussion',
                'id': discussion.id,
                'title': discussion.title,
                'content': discussion.content[:200] + '...',  # Truncate content
                'views': discussion.views,
                'url': url_for('discussions.view_discussion', discussion_id=discussion.id)
            })
    
    return jsonify(results)

@bp.route('/api/chat', methods=['POST'])
def chat_with_ai():
    data = request.json
    if 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        You are an educational assistant. Please help with this question:
        
        {data['message']}
        
        Provide a clear and helpful response.
        """
        
        response = model.generate_content(prompt)
        return jsonify({'response': response.text})
    
    except Exception as e:
        return jsonify({'error': 'Failed to generate AI response'}), 500

@bp.route('/api/rephrase', methods=['POST'])
def rephrase_text():
    data = request.json
    if 'text' not in data:
        return jsonify({'error': 'Text is required'}), 400
    
    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Rephrase this text to be more polite and professional while maintaining its meaning:
        
        {data['text']}
        
        Provide only the rephrased version without any additional text.
        """
        
        response = model.generate_content(prompt)
        return jsonify({'rephrased_text': response.text})
    
    except Exception as e:
        return jsonify({'error': 'Failed to rephrase text'}), 500

@bp.route('/api/analyze-content', methods=['POST'])
def analyze_content():
    data = request.json
    if 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400
    
    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Analyze this educational content and extract:
        1. Main subjects
        2. Key chapters/topics
        3. Educational level
        4. Board/curriculum (if mentioned)
        5. Country (if mentioned)
        
        Content: {data['content'][:5000]}  # Limit content length
        
        Provide a structured response.
        """
        
        response = model.generate_content(prompt)
        return jsonify({'analysis': response.text})
    
    except Exception as e:
        return jsonify({'error': 'Failed to analyze content'}), 500

@bp.route('/sitemap.xml')
def sitemap():
    """Generate a sitemap.xml file for search engines"""
    try:
        # Create a list of URLs to include in the sitemap
        pages = []
        
        # Add static pages
        host_base = request.host_url.rstrip('/')
        static_pages = [
            {'loc': url_for('main.index')},
            {'loc': url_for('main.about')},
            {'loc': url_for('main.contact')},
            {'loc': url_for('main.faq')},
            {'loc': url_for('main.terms')},
            {'loc': url_for('main.privacy')},
            {'loc': url_for('resources.list_resources')},
            {'loc': url_for('discussions.list_discussions')}
        ]
        
        for page in static_pages:
            page['loc'] = host_base + page['loc']
            page['lastmod'] = datetime.now().strftime('%Y-%m-%d')
            page['changefreq'] = 'weekly'
            page['priority'] = '0.8'
            pages.append(page)
        
        # Add dynamic resource pages (limit to 1000 most viewed for performance)
        resources = current_app.db.resources.find().sort('views', -1).limit(1000)
        for resource_data in resources:
            resource = Resource(resource_data)
            page = {
                'loc': host_base + url_for('resources.view_resource', resource_id=resource.id),
                'lastmod': resource_data.get('updated_at', resource_data.get('created_at', datetime.now())).strftime('%Y-%m-%d'),
                'changefreq': 'monthly',
                'priority': '0.7'
            }
            pages.append(page)
        
        # Add dynamic discussion pages (limit to 500 most active for performance)
        discussions = current_app.db.discussions.find({'status': 'active'}).sort('updated_at', -1).limit(500)
        for discussion_data in discussions:
            discussion = Discussion(discussion_data)
            page = {
                'loc': host_base + url_for('discussions.view_discussion', discussion_id=discussion.id),
                'lastmod': discussion_data.get('updated_at', discussion_data.get('created_at', datetime.now())).strftime('%Y-%m-%d'),
                'changefreq': 'weekly',
                'priority': '0.6'
            }
            pages.append(page)
        
        # Generate the XML content
        xml_content = render_template('sitemap.xml', pages=pages)
        return Response(xml_content, mimetype='application/xml')
    except Exception as e:
        current_app.logger.error(f"Error generating sitemap: {str(e)}")
        return Response("Error generating sitemap", status=500)

@bp.route('/robots.txt')
def robots():
    """Generate a robots.txt file for search engines"""
    host_base = request.host_url.rstrip('/')
    robots_content = f"""User-agent: *
Allow: /
Allow: /resources/
Allow: /resource/
Allow: /discussions/
Allow: /discussion/
Allow: /about
Allow: /contact
Allow: /faq
Allow: /terms
Allow: /privacy

Disallow: /auth/login
Disallow: /auth/register
Disallow: /admin/
Disallow: /user/
Disallow: /monetization/

Sitemap: {host_base}/sitemap.xml
"""
    return Response(robots_content, mimetype='text/plain') 