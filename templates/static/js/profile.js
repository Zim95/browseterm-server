// User Profile JavaScript
console.log('User profile page loaded successfully!');

// Dummy user data
const dummyUserData = {
    "user": {
        "name": "Namah Shrestha",
        "email": "test@gmail.com"
    }
};

// Dummy current plan data
const dummyCurrentPlanData = {
    "currentPlan": {
        "id": "free",
        "name": "Free"
    }
};

// Function to simulate API call for user data
async function fetchUser() {
    console.log('Fetching user data...');
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Return dummy data (in real app, this would be a fetch() call)
    return dummyUserData;
}

// Function to simulate API call for current plan
async function fetchCurrentPlan() {
    console.log('Fetching current plan...');
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Return dummy data (in real app, this would be a fetch() call)
    return dummyCurrentPlanData;
}

// Function to load user profile data
async function loadUserProfile() {
    try {
        // Fetch both user data and current plan in parallel
        const [userData, currentPlanData] = await Promise.all([
            fetchUser(),
            fetchCurrentPlan()
        ]);
        
        console.log('User data loaded:', userData.user);
        console.log('Current plan:', currentPlanData.currentPlan);
        
        // Update UI with fetched data
        updateUserProfile(userData.user, currentPlanData.currentPlan);
    } catch (error) {
        console.error('Error loading user profile:', error);
        showError('Error loading user profile. Please try again.');
    }
}

// Function to update user profile UI
function updateUserProfile(user, currentPlan) {
    // Update user details
    document.getElementById('userName').textContent = user.name;
    document.getElementById('userEmail').textContent = user.email;
    document.getElementById('currentPlan').textContent = currentPlan.name;
    
    // Remove loading state
    document.getElementById('userName').classList.remove('loading');
    document.getElementById('userEmail').classList.remove('loading');
    document.getElementById('currentPlan').classList.remove('loading');
}

// Function to show error message
function showError(message) {
    const userName = document.getElementById('userName');
    const userEmail = document.getElementById('userEmail');
    const currentPlan = document.getElementById('currentPlan');
    
    userName.textContent = message;
    userEmail.textContent = message;
    currentPlan.textContent = message;
    
    userName.classList.add('loading');
    userEmail.classList.add('loading');
    currentPlan.classList.add('loading');
}

// Function to handle photo upload
function handlePhotoUpload() {
    const fileInput = document.getElementById('photoUpload');
    const profilePhoto = document.getElementById('profilePhoto');
    
    fileInput.addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (file) {
            // Validate file type
            if (!file.type.startsWith('image/')) {
                alert('Please select a valid image file.');
                return;
            }
            
            // Validate file size (max 5MB)
            if (file.size > 5 * 1024 * 1024) {
                alert('File size must be less than 5MB.');
                return;
            }
            
            // Create image preview
            const reader = new FileReader();
            reader.onload = function(e) {
                // Remove icon and add image
                const icon = profilePhoto.querySelector('.photo-icon');
                if (icon) {
                    icon.remove();
                }
                
                // Create or update image
                let img = profilePhoto.querySelector('img');
                if (!img) {
                    img = document.createElement('img');
                    profilePhoto.appendChild(img);
                }
                img.src = e.target.result;
                
                console.log('Profile photo updated:', file.name);
            };
            reader.readAsDataURL(file);
        }
    });
}

// Function to attach event listeners
function attachEventListeners() {
    // Upload button click
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('photoUpload');
    
    uploadBtn.addEventListener('click', function() {
        fileInput.click();
    });
    
    // Profile photo click
    const profilePhoto = document.getElementById('profilePhoto');
    profilePhoto.addEventListener('click', function() {
        fileInput.click();
    });
    
    // Handle photo upload
    handlePhotoUpload();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('User profile DOM is ready');
    
    // Load user profile data
    loadUserProfile();
    
    // Attach event listeners
    attachEventListeners();
});
