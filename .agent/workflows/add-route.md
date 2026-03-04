---
description: Add or update a Flask route in MedTrack (in both app.py for local and aws_setup.py for EC2)
---

## Prerequisites
- Understanding of Flask routing
- Route to be added to both `app.py` (dev) and `aws_setup.py` (EC2 production)
- Template file created if a new page is needed

## Steps

1. Identify and plan the route
   - Determine the URL path (e.g., `/patient/newfeature`)
   - Determine the HTTP methods (GET, POST, or both)
   - Determine the required session role (patient, doctor, admin)
   - Identify the template to render

2. Add the route to `app.py` (local development file)
   - Open `c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack\app.py`
   - Add the route before the last `if __name__ == '__main__':` block
   - Follow this template:
   ```python
   @app.route('/your/path', methods=['GET', 'POST'])
   def your_function_name():
       if 'user_id' not in session:
           flash('Please login first.', 'error')
           return redirect(url_for('login'))
       # your logic here
       return render_template('your_template.html',
                              current_user=session.get('user_name'),
                              current_role=session.get('role'))
   ```

3. Add the same route to `aws_setup.py` (EC2 production file)
   - Open `c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack\aws_setup.py`
   - Add the identical route before the `if __name__ == '__main__':` block at the end

4. If the route renders a new template, create the HTML file
   - Create `templates/your_template.html`
   - Start with: `{% extends "base.html" %} {% block content %} ... {% endblock %}`

5. If the route is linked from the sidebar, add it to `base.html`
   - Open `templates/base.html`
   - Add `url_for('your_function_name')` in the appropriate section (patient or doctor)

6. Test locally
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000/your/path`

7. Push to GitHub and deploy to EC2
   - Run `/push-github` workflow
   - Run `/deploy-ec2` workflow
