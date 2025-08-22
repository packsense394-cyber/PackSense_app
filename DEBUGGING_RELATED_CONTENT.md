# Debugging Related Sentences and Images Issue 🔍

## 🚨 **Current Issue**
- **Problem**: Related sentences and images are not appearing when clicking on co-occurrence network nodes
- **Symptom**: Info panel shows default content but no related content when nodes are clicked
- **Status**: Co-occurrence network displays correctly, but related content is missing

## 🔧 **Debugging Steps Applied**

### **1. Added Backend Debugging** ✅
```python
# Added to app.py to verify data generation
print(f"Built keyword sentence map with {len(kw_sent)} keywords")
if kw_sent:
    print(f"Sample keyword sentence map keys: {list(kw_sent.keys())[:5]}")
    for key in list(kw_sent.keys())[:3]:
        print(f"  {key}: {len(kw_sent[key])} sentences")

print(f"Built keyword image map with {len(kw_img_trans)} keywords")
if kw_img_trans:
    print(f"Sample keyword image map keys: {list(kw_img_trans.keys())[:5]}")
    for key in list(kw_img_trans.keys())[:3]:
        print(f"  {key}: {len(kw_img_trans[key])} images")
```

### **2. Added Frontend Debugging** ✅
```javascript
// Added to showNodeDetails function
console.log('Raw keyword sentence map:', keywordSentenceMap);
console.log('Raw keyword image map:', keywordImageMap);
console.log('Keyword sentence map keys:', Object.keys(keywordSentenceMap));
console.log('Keyword image map keys:', Object.keys(keywordImageMap));
```

### **3. Added Case-Sensitive Matching** ✅
```javascript
// Try different case variations for node names
let relatedReviews = keywordSentenceMap[node.name] || [];
if (relatedReviews.length === 0) {
    // Try lowercase
    relatedReviews = keywordSentenceMap[node.name.toLowerCase()] || [];
}
if (relatedReviews.length === 0) {
    // Try to find by partial match
    const matchingKey = Object.keys(keywordSentenceMap).find(key => 
        key.toLowerCase() === node.name.toLowerCase()
    );
    if (matchingKey) {
        relatedReviews = keywordSentenceMap[matchingKey] || [];
    }
}
```

## 🔍 **What to Check**

### **1. Backend Console Output**
When you run the analysis, check the terminal output for:
- `Built keyword sentence map with X keywords`
- `Sample keyword sentence map keys: [...]`
- `Built keyword image map with X keywords`
- `Sample keyword image map keys: [...]`

**Expected**: Should show non-zero counts and sample keys

### **2. Browser Console Output**
When you click on a node, check the browser console for:
- `showNodeDetails called for node: [node_name]`
- `Raw keyword sentence map: {...}`
- `Raw keyword image map: {...}`
- `Keyword sentence map keys: [...]`
- `Keyword image map keys: [...]`
- `Related reviews for [node_name]: [...]`
- `Related images for [node_name]: [...]`

**Expected**: Should show data in the maps and non-zero counts

### **3. Data Structure Verification**
Check if the data structures match:
- **Node names**: What are the actual node names in the network?
- **Keyword map keys**: What are the keys in the keyword maps?
- **Case sensitivity**: Are the node names and map keys using the same case?

## 🎯 **Potential Issues and Solutions**

### **Issue 1: No Data Generated**
**Symptoms**: Backend shows "0 keywords" or "No data found"
**Solution**: Check if reviews contain the packaging keywords

### **Issue 2: Data Not Passed to Template**
**Symptoms**: Backend shows data but browser console shows empty objects
**Solution**: Check template variable names and JSON serialization

### **Issue 3: Case Mismatch**
**Symptoms**: Data exists but node names don't match map keys
**Solution**: The case-sensitive matching code should handle this

### **Issue 4: Empty Data**
**Symptoms**: Maps exist but contain empty arrays
**Solution**: Check if the keyword matching logic is working correctly

## 🚀 **Testing Instructions**

### **Step 1: Run Analysis**
1. Run a new analysis on a product
2. Check terminal output for keyword map generation
3. Note the counts and sample keys

### **Step 2: Open Co-occurrence Network**
1. Click on "Co-occurrence Network" button
2. Open browser developer tools (F12)
3. Go to Console tab

### **Step 3: Click on Nodes**
1. Click on different nodes in the network
2. Check console output for debugging information
3. Look for any error messages

### **Step 4: Verify Data**
1. Compare node names with keyword map keys
2. Check if related content arrays have data
3. Verify the data structure matches expectations

## 📊 **Expected Results**

### **If Working Correctly**
- Backend shows keyword maps with data
- Browser console shows node click events
- Related content arrays contain data
- Info panel displays sentences and images

### **If Not Working**
- Check which step fails
- Look for error messages
- Verify data generation and passing

## 🔧 **Next Steps**

Based on the debugging output:
1. **If no data generated**: Fix keyword matching logic
2. **If data not passed**: Fix template variable passing
3. **If case mismatch**: The case-sensitive matching should handle this
4. **If empty arrays**: Fix the keyword sentence/image mapping functions

**Please run the analysis and check both the terminal output and browser console to identify where the issue occurs.**
