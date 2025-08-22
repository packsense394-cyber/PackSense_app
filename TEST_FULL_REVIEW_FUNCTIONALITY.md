# Testing Full Review Display Functionality 🧪

## 🎯 **Current Setup**
- **Initial Display**: Shows sentence with keyword highlighted (✅ Working)
- **Full Review Display**: Should show complete review when "Show Full Review" is clicked
- **Review Information**: Should include reviewer name, date, rating, and full review text

## 🔍 **What to Test**

### **Step 1: Open Co-occurrence Network**
1. Run analysis on a product
2. Click "Co-occurrence Network" button
3. Click on any node (e.g., "plastic")

### **Step 2: Check Initial Display**
- Should see sentence with keyword highlighted in yellow
- Should see "Show Full Review" button
- Should see reviewer name and date in header

### **Step 3: Test Full Review Display**
1. Click "Show Full Review" button
2. **Expected Result**: 
   - Full review text should appear
   - Reviewer name should be displayed
   - Date should be formatted properly
   - Star rating should be shown
   - Keyword should be highlighted in full text
   - Button should change to "Show Less"

### **Step 4: Check Browser Console**
Open browser developer tools (F12) and check console for:
```
Toggle review display - review data: {...}
Review text length: [number]
Reviewer name: [name]
Review date: [date]
Review rating: [rating]
```

## 🚨 **Potential Issues**

### **Issue 1: No Full Review Data**
**Symptoms**: Clicking "Show Full Review" shows nothing or error
**Debug**: Check console for "No filtered reviews available" error
**Solution**: Verify that `relatedReviewsData` contains full review information

### **Issue 2: Missing Review Information**
**Symptoms**: Full review shows but missing name/date/rating
**Debug**: Check console logs for review data structure
**Solution**: Verify that review data includes all required fields

### **Issue 3: Button Not Working**
**Symptoms**: Clicking button does nothing
**Debug**: Check for JavaScript errors in console
**Solution**: Verify that `toggleReviewDisplay` function is being called

## 🔧 **Debugging Steps**

### **If Full Review Not Showing:**
1. Check browser console for errors
2. Verify that `window.currentFilteredReviews` contains data
3. Check that `review.review_text` exists and has content
4. Verify that the `fullReviewDiv` element exists

### **If Review Data Missing:**
1. Check that `relatedReviewsData` is being populated correctly
2. Verify that `review_index` is being used to get original review data
3. Check that the main `reviews` array contains complete information

## 📊 **Expected Data Structure**

The `relatedReviewsData` should contain:
```javascript
{
    sentence: "The specific sentence with keyword",
    review_text: "The complete review text",
    review_title: "Review title",
    review_index: 123
}
```

The `toggleReviewDisplay` function should receive:
```javascript
{
    reviewer_name: "Reviewer Name",
    review_date: "2024-01-15",
    review_rating: 4,
    review_text: "Complete review text...",
    sentence: "Sentence with keyword"
}
```

## 🎯 **Test Cases**

### **Test Case 1: Basic Functionality**
- Click on node with reviews
- Click "Show Full Review"
- Verify full text appears

### **Test Case 2: Multiple Reviews**
- Click on node with multiple reviews
- Test pagination
- Verify each review shows full text

### **Test Case 3: Review Information**
- Verify reviewer name appears
- Verify date is formatted correctly
- Verify star rating displays
- Verify keyword highlighting works

## 🚀 **Next Steps**

If the functionality is working:
- ✅ Full review display is operational
- ✅ All review information is shown
- ✅ Keyword highlighting works in full text

If not working:
- 🔧 Check console for specific errors
- 🔧 Verify data structure
- 🔧 Test with different nodes
- 🔧 Check browser compatibility

**Please test the functionality and report any issues found!**
