# JavaScript Test Suite

## 🎯 Overview

Custom JavaScript test runner with a beautiful UI matching BrowseTerm's theme.

## 📂 File Structure

```
templates/
├── js_test.html                    # Main test page template
└── static/
    ├── css/
    │   └── js_test.css             # Custom test UI styling
    └── js/
        └── js_tests/
            ├── js_test_runner.js   # Custom test runner UI
            ├── test_base_class.js  # Tests for base_class.js
            ├── test_oauth_callback.js  # Tests for oauth_callback.js
            ├── test_login.js       # Tests for login.js
            ├── test_profile.js     # Tests for profile.js
            └── test_home.js        # Tests for home.js
```

## 🚀 How to Access

Navigate to: **`http://localhost:9999/js-test`**

This is a **hidden route** - not visible in the sidebar navigation.

## ✨ Features

### UI Components:
- **Test Summary Stats**: Total, Passed, Failed, Duration
- **Test File Cards**: One card per test file
- **Progress Bars**: Visual progress for each test file
- **Collapsible Logs**: Toggle to show/hide test logs
- **Status Badges**: Running/Passed/Failed states
- **Dark Mode Support**: Matches your app's theme

### Each Test Card Shows:
```
test_base_class.js          5/6 tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━ (Progress bar)
▶ Show Logs
```

## 🧪 Writing Tests

Tests use **Mocha + Chai** (BDD style):

```javascript
describe('YourClass', function() {
    
    it('should do something', function() {
        const result = YourClass.method();
        expect(result).to.equal('expected value');
    });
    
    it('should handle errors', function() {
        expect(() => YourClass.badMethod()).to.throw();
    });
});
```

## 📝 Adding New Tests

1. Create a new test file in `js_tests/` directory:
   ```bash
   touch templates/static/js/js_tests/test_yourfile.js
   ```

2. Write your tests:
   ```javascript
   describe('YourFile', function() {
       it('should test something', function() {
           expect(true).to.be.true;
       });
   });
   ```

3. Register in `js_test.html`:
   ```html
   <!-- Load your JS file -->
   <script src="{{ url_for('static', path='/js/yourfile.js') }}"></script>
   
   <!-- Load your test file -->
   <script src="{{ url_for('static', path='/js/js_tests/test_yourfile.js') }}"></script>
   ```

4. Update `js_test_runner.js` testFiles array:
   ```javascript
   this.testFiles = [
       // ... existing files
       { name: 'test_yourfile.js', displayName: 'Your File Tests', suite: 'Your File' }
   ];
   ```

## 🎨 Color Theme

Automatically matches your app's light/dark mode:
- **Light Mode**: Clean, minimal design
- **Dark Mode**: Easy on the eyes with good contrast

## 📊 Test Results

### Visual Indicators:
- ✅ **Green progress bar** = All tests passing
- ❌ **Red progress bar** = Some tests failing
- 🔵 **Blue badge** = Tests running
- **Pulsing animation** = Active test execution

### Logs:
- Click "Show Logs" to see detailed results
- Each log entry shows:
  - Test name
  - Pass/Fail status
  - Error messages (if failed)
  - Stack traces (if failed)
  - Duration

## 🔧 Technology Stack

- **Mocha 10.2.0** - Test framework
- **Chai 4.3.10** - Assertion library
- **Custom UI** - No default Mocha reporter
- **Pure JavaScript** - No build tools needed
- **CDN delivery** - No npm packages to install

## 💡 Tips

1. **Auto-run**: Tests run automatically when you load the page
2. **Re-run**: Click "▶️ Run All Tests" button to re-run
3. **Focus**: Expand logs to debug failing tests
4. **Hidden**: Route is not in sidebar - bookmark it!
5. **Offline**: Works without internet (except CDN dependencies)

## 🐛 Debugging

If tests fail:
1. Click "Show Logs" on the failing test card
2. Read the error message
3. Check the stack trace
4. Fix the issue
5. Refresh the page

## 📦 Current Test Coverage

- ✅ **base_class.js**: 24 tests
  - BaseUtilities: 5 tests
  - NotificationManager: 6 tests
  - DarkModeManager: 3 tests
  - LogoutManager: 2 tests
  - UIAnimationManager: 4 tests

- ✅ **oauth_callback.js**: 7 tests
  - OAuthCallbackHandler: 7 tests

- 📝 **login.js**: 2 placeholder tests
- 📝 **profile.js**: 2 placeholder tests
- 📝 **home.js**: 2 placeholder tests

**Add more tests as you build new features!**

