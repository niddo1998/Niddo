import re
import os

files = ['templates/admin_dashboard.html', 'templates/vecino_dashboard.html']

for file in files:
    if not os.path.exists(file): continue
    with open(file, 'r') as f:
        content = f.read()

    # Update fonts
    content = content.replace("family=Inter:wght@400;500;600;700;800", "family=Fredoka:wght@400;500;600;700|Nunito+Sans:wght@400;600;700")
    content = content.replace("font-family: 'Inter'", "font-family: 'Nunito Sans'")
    content = content.replace("font-family:'Inter'", "font-family:'Nunito Sans'")
    
    # We want titles to be Fredoka
    content = re.sub(r'(\.page-title \{.*?)(\})', r"\1 font-family: 'Fredoka', sans-serif; \2", content)
    content = re.sub(r'(\.sidebar-brand \{.*?)(\})', r"\1 font-family: 'Fredoka', sans-serif; \2", content)
    
    # Update colors
    content = re.sub(r'--bg: #[0-9A-Fa-f]{6};', '--bg: #f8f5ee;', content)
    content = re.sub(r'--text: #[0-9A-Fa-f]{6};', '--text: #211812;', content)
    content = re.sub(r'--blue: #[0-9A-Fa-f]{6};', '--blue: #e05d41;', content) # Terracota
    content = re.sub(r'--blue-light: #[0-9A-Fa-f]{6};', '--blue-light: #e67d65;', content) 
    content = re.sub(r'--blue-dark: #[0-9A-Fa-f]{6};', '--blue-dark: #c5482e;', content)
    content = re.sub(r'--purple: #[0-9A-Fa-f]{6};', '--purple: #155140;', content) # Verde Nido
    content = re.sub(r'--purple-light: #[0-9A-Fa-f]{6};', '--purple-light: #227b62;', content)
    
    # Increase border radius for "Iconos redondeados"
    content = content.replace("border-radius: 10px;", "border-radius: 16px;")
    content = content.replace("border-radius: 8px;", "border-radius: 12px;")
    content = content.replace("border-radius: 7px;", "border-radius: 12px;")
    
    with open(file, 'w') as f:
        f.write(content)

