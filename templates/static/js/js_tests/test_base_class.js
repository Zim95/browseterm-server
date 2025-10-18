/**
 * Tests for base_class.js
 */

describe('Base Class', function() {
    
    describe('BaseUtilities', function() {
        
        beforeEach(function() {
            // Clear localStorage before each test
            localStorage.clear();
        });
        
        it('should get value from localStorage', function() {
            localStorage.setItem('testKey', 'testValue');
            const result = BaseUtilities.getFromLocalStorage('testKey');
            expect(result).to.equal('testValue');
        });
        
        it('should return default value when key not found', function() {
            const result = BaseUtilities.getFromLocalStorage('nonExistent', 'default');
            expect(result).to.equal('default');
        });
        
        it('should set value in localStorage', function() {
            BaseUtilities.setInLocalStorage('newKey', 'newValue');
            const stored = localStorage.getItem('newKey');
            expect(stored).to.equal('newValue');
        });
        
        it('should remove value from localStorage', function() {
            localStorage.setItem('removeMe', 'value');
            BaseUtilities.removeFromLocalStorage('removeMe');
            const result = localStorage.getItem('removeMe');
            expect(result).to.be.null;
        });
        
        it('should detect mobile viewport', function() {
            expect(BaseUtilities.isMobile).to.be.a('function');
            const isMobile = BaseUtilities.isMobile();
            expect(isMobile).to.be.a('boolean');
        });
    });
    
    describe('NotificationManager', function() {
        
        let notificationManager;
        
        beforeEach(function() {
            // Create notification container if it doesn't exist
            let container = document.getElementById('notificationContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'notificationContainer';
                document.body.appendChild(container);
            }
            notificationManager = new NotificationManager();
        });
        
        it('should create NotificationManager instance', function() {
            expect(notificationManager).to.be.instanceOf(NotificationManager);
            expect(notificationManager.container).to.not.be.null;
        });
        
        it('should generate unique IDs', function() {
            const id1 = notificationManager.generateId();
            const id2 = notificationManager.generateId();
            expect(id1).to.not.equal(id2);
            expect(id1).to.include('notification_');
            expect(id2).to.include('notification_');
        });
        
        it('should have default duration of 5000ms', function() {
            expect(notificationManager.defaultDuration).to.equal(5000);
        });
        
        it('should create notification element', function() {
            const notification = notificationManager.createNotificationElement({
                id: 'test123',
                type: 'success',
                title: 'Test Title',
                message: 'Test Message',
                closable: true,
                icon: '✓'
            });
            
            expect(notification).to.be.instanceOf(HTMLElement);
            expect(notification.className).to.include('notification');
            expect(notification.className).to.include('success');
        });
        
        it('should have convenience methods', function() {
            expect(notificationManager.success).to.be.a('function');
            expect(notificationManager.error).to.be.a('function');
            expect(notificationManager.info).to.be.a('function');
            expect(notificationManager.warning).to.be.a('function');
        });
    });
    
    describe('DarkModeManager', function() {
        
        let darkModeManager;
        
        beforeEach(function() {
            localStorage.clear();
            document.body.classList.remove('dark-mode');
            darkModeManager = new DarkModeManager();
        });
        
        it('should create DarkModeManager instance', function() {
            expect(darkModeManager).to.be.instanceOf(DarkModeManager);
        });
        
        it('should initialize with default light theme', function() {
            darkModeManager.initialize();
            const theme = localStorage.getItem('theme');
            expect(theme).to.equal('light');
        });
        
        it('should apply dark mode from localStorage', function() {
            localStorage.setItem('theme', 'dark');
            darkModeManager.initialize();
            expect(document.body.classList.contains('dark-mode')).to.be.true;
        });
    });
    
    describe('LogoutManager', function() {
        
        let logoutManager;
        
        beforeEach(function() {
            logoutManager = new LogoutManager();
        });
        
        it('should create LogoutManager instance', function() {
            expect(logoutManager).to.be.instanceOf(LogoutManager);
        });
        
        it('should have handleLogout method', function() {
            expect(logoutManager.handleLogout).to.be.a('function');
        });
    });
    
    describe('UIAnimationManager', function() {

        let uiAnimationManager;

        beforeEach(function() {
            uiAnimationManager = new UIAnimationManager();
        });

        it('should create UIAnimationManager instance', function() {
            expect(uiAnimationManager).to.be.instanceOf(UIAnimationManager);
        });

        it('should have initialize method', function() {
            expect(uiAnimationManager.initialize).to.be.a('function');
        });

        it('should have addMenuLinkAnimations method', function() {
            expect(uiAnimationManager.addMenuLinkAnimations).to.be.a('function');
        });

        it('should have addButtonAnimations method', function() {
            expect(uiAnimationManager.addButtonAnimations).to.be.a('function');
        });
    });
});

