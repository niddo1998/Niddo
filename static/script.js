// Function to switch between sections
function showSection(section) {
    // Prevent default behavior
    if (event) {
        event.preventDefault();
    }
    
    // Hide all page sections
    document.getElementById('administradores-section').style.display = 'none';
    document.getElementById('vecinos-section').style.display = 'none';
    document.getElementById('proveedores-section').style.display = 'none';
    
    // Show selected section
    document.getElementById(section + '-section').style.display = 'block';
    
    // Scroll to top smoothly
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
    
    // Update active nav link
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        link.classList.remove('active', 'vecinos-active', 'proveedores-active');
    });
    
    // Find the clicked link and add active class
    const clickedLink = event.target;
    clickedLink.classList.add('active');
    
    // Add specific active class for color theming
    if (section === 'vecinos') {
        clickedLink.classList.add('vecinos-active');
    } else if (section === 'proveedores') {
        clickedLink.classList.add('proveedores-active');
    }
}

// Smooth scrolling for navigation links
document.addEventListener('DOMContentLoaded', function() {
    // Add fade-in animation to elements
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
            }
        });
    }, observerOptions);

    // Observe all feature cards and testimonial cards
    document.querySelectorAll('.feature-card, .testimonial-card').forEach(el => {
        observer.observe(el);
    });

    // Navbar background on scroll
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            navbar.style.background = 'rgba(255, 255, 255, 0.98)';
            navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.05)';
        }
    });

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const offsetTop = target.offsetTop - 80;
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    // Video button modal (placeholder functionality)
    const videoBtn = document.querySelector('.hero-content .btn-primary');
    if (videoBtn) {
        videoBtn.addEventListener('click', function() {
            alert('Video functionality would be implemented here. This is a demo version.');
        });
    }

    // Demo request buttons
    document.querySelectorAll('.btn').forEach(btn => {
        if (btn.textContent.includes('Demo') || btn.textContent.includes('Empezá')) {
            btn.addEventListener('click', function(e) {
                if (!this.classList.contains('navbar-toggler')) {
                    e.preventDefault();
                    showDemoModal();
                }
            });
        }
    });

    // Animated counter for statistics
    function animateCounter(element, target, duration = 2000) {
        let start = 0;
        const increment = target / (duration / 16);
        const timer = setInterval(() => {
            start += increment;
            if (start >= target) {
                element.textContent = '+' + target;
                clearInterval(timer);
            } else {
                element.textContent = '+' + Math.floor(start);
            }
        }, 16);
    }

    // Trigger counter animation when stats section is visible
    const statsObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.classList.contains('animated')) {
                const statElement = entry.target.querySelector('strong');
                if (statElement && statElement.textContent.includes('+300')) {
                    animateCounter(statElement, 300);
                    entry.target.classList.add('animated');
                }
            }
        });
    }, { threshold: 0.5 });

    const statsSection = document.querySelector('.stats');
    if (statsSection) {
        statsObserver.observe(statsSection);
    }

    // Add hover effect to cards
    document.querySelectorAll('.feature-card, .testimonial-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-15px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Form validation for demo request (placeholder)
    function showDemoModal() {
        const modalHtml = `
            <div class="modal fade" id="demoModal" tabindex="-1" aria-labelledby="demoModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header border-0">
                            <h5 class="modal-title" id="demoModalLabel">Solicitar Demo</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="demoForm">
                                <div class="mb-3">
                                    <label for="name" class="form-label">Nombre completo</label>
                                    <input type="text" class="form-control" id="name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="email" class="form-label">Email</label>
                                    <input type="email" class="form-control" id="email" required>
                                </div>
                                <div class="mb-3">
                                    <label for="phone" class="form-label">Teléfono</label>
                                    <input type="tel" class="form-control" id="phone" required>
                                </div>
                                <div class="mb-3">
                                    <label for="consorcio" class="form-label">Nombre del consorcio</label>
                                    <input type="text" class="form-control" id="consorcio" required>
                                </div>
                                <div class="mb-3">
                                    <label for="message" class="form-label">Mensaje (opcional)</label>
                                    <textarea class="form-control" id="message" rows="3"></textarea>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer border-0">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-primary" onclick="submitDemoForm()">Enviar solicitud</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existingModal = document.getElementById('demoModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('demoModal'));
        modal.show();
    }

    // Submit demo form (placeholder)
    window.submitDemoForm = function() {
        const form = document.getElementById('demoForm');
        if (form.checkValidity()) {
            alert('¡Gracias por tu interés! Nos contactaremos a la brevedad.');
            const modal = bootstrap.Modal.getInstance(document.getElementById('demoModal'));
            modal.hide();
        } else {
            form.reportValidity();
        }
    };

    // Add parallax effect to hero section
    window.addEventListener('scroll', function() {
        const scrolled = window.pageYOffset;
        const heroSection = document.querySelector('.hero-section');
        if (heroSection) {
            heroSection.style.transform = `translateY(${scrolled * 0.5}px)`;
        }
    });

    // Add loading animation
    window.addEventListener('load', function() {
        document.body.classList.add('loaded');
    });

    // Mobile menu handling
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
            setTimeout(() => {
                if (navbarCollapse.classList.contains('show')) {
                    navbarToggler.classList.add('active');
                } else {
                    navbarToggler.classList.remove('active');
                }
            }, 10);
        });

        // Close mobile menu when clicking on a link
        document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
            link.addEventListener('click', function() {
                const collapse = bootstrap.Collapse.getInstance(navbarCollapse);
                if (collapse) {
                    collapse.hide();
                }
            });
        });
    }

    // Add tooltip functionality
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    console.log('Niddo landing page loaded successfully!');
});
