# Testing Guide: Patient ID Generation and Customer Creation

This guide explains how to test the patient ID generation feature when creating customers in Odoo.

## Prerequisites

1. Odoo is running with the `abershum-elis-sync` module installed
2. Module is properly installed and activated
3. OpenELIS is accessible (for test order sync testing)

## Testing Patient ID Generation

### Step 1: Verify Module Installation

1. Go to **Apps** menu in Odoo
2. Remove the "Apps" filter and search for "Abershum ELIS Sync"
3. Verify the module is **Installed** (green checkmark)
4. If not installed, click **Install**

### Step 2: Verify Sequence Creation

1. Go to **Settings** → **Technical** → **Sequences & Identifiers** → **Sequences**
2. Search for "Patient ID Sequence"
3. Verify the sequence exists with:
   - **Code**: `abershum.patient.id.sequence`
   - **Prefix**: `P`
   - **Padding**: `6`
   - **Next Number**: `1` (or current number)

### Step 3: Create a New Customer/Patient

1. Navigate to **Sales** → **Customers**
2. Click **Create** button
3. Fill in customer details:
   - **Name**: `John Doe`
   - **Phone**: `1234567890`
   - **Email**: `john.doe@example.com`
   - **Is a Company**: Leave unchecked (for individual patient)
   - **Customer**: Should be checked by default
4. **DO NOT** manually enter anything in the **Internal Reference** field
5. Click **Save**

### Step 4: Verify Patient ID Generation

After saving, verify:

1. **Check Internal Reference Field**:
   - The **Internal Reference** (`ref`) field should be automatically populated
   - Format should be: `P000001` (or next number in sequence)
   - The patient ID should be visible in the customer form

2. **Check Customer Display Name**:
   - The customer name should display as: `John Doe [P000001]`
   - This indicates the patient ID is properly associated

3. **Verify Uniqueness**:
   - Try creating another customer
   - The new customer should get the next patient ID: `P000002`
   - Each customer should have a unique patient ID

### Step 5: Test Patient ID Search

1. In the **Customers** list view, use the search bar
2. Search for `P000001` (the generated patient ID)
3. The customer "John Doe" should appear in search results
4. This confirms the patient ID is searchable

### Step 6: Test Manual Patient ID Entry (Optional)

1. Create a new customer
2. **Manually enter** a patient ID in the **Internal Reference** field: `P999999`
3. Save the customer
4. Verify:
   - The manually entered ID is preserved (not overwritten)
   - No automatic generation occurs when `ref` is already provided

## Testing Patient Sync to OpenELIS

### Step 1: Configure OpenELIS Sync

1. Go to **Settings** → **OpenELIS Integration**
2. Enable **Enable OpenELIS Test Order Sync**
3. Enter **OpenELIS API URL**: `http://openelis:8080/openelis` (or your OpenELIS URL)
4. Enter **OpenELIS API Username** and **Password** (if required)
5. Click **Save**

### Step 2: Create a Test Order

1. Go to **Sales** → **Orders** → **Quotations**
2. Click **Create**
3. Select the customer you created (with patient ID `P000001`)
4. Add a product that belongs to:
   - Category: `Services/Lab/Test` OR
   - Category: `Services/Lab/Panel`
5. Click **Confirm** to confirm the sale order

### Step 3: Verify Sync to OpenELIS

1. Check Odoo logs for sync messages:
   - Look for: `"Successfully synced sale order ... to OpenELIS"`
   - Or check for errors in logs

2. Check OpenELIS:
   - Log into OpenELIS
   - Search for patient with identifier `P000001`
   - Verify the patient exists in OpenELIS
   - Verify the test order/sample was created

## Troubleshooting

### Patient ID Not Generated

**Symptoms**: Customer created but `ref` field is empty

**Solutions**:
1. Check if sequence exists: **Settings** → **Technical** → **Sequences**
2. Verify sequence code: `abershum.patient.id.sequence`
3. Check Odoo logs for errors
4. Verify module is properly installed
5. Try upgrading the module: **Apps** → **Upgrade**

### Duplicate Patient ID Error

**Symptoms**: Error message: "Internal Reference for Customer should be unique!"

**Solutions**:
1. This is expected behavior - patient IDs must be unique
2. If you see this error, it means:
   - The patient ID already exists, OR
   - There's a conflict in the sequence
3. Check existing customers for duplicate patient IDs
4. Reset sequence if needed: **Settings** → **Technical** → **Sequences** → Edit sequence → Reset **Next Number**

### Patient ID Format Issues

**Symptoms**: Patient ID doesn't match expected format (e.g., `P000001`)

**Solutions**:
1. Check sequence configuration:
   - **Prefix**: Should be `P`
   - **Padding**: Should be `6`
2. Edit sequence if needed: **Settings** → **Technical** → **Sequences** → Edit

### Test Order Not Syncing

**Symptoms**: Order confirmed but not appearing in OpenELIS

**Solutions**:
1. Verify sync is enabled in **Settings** → **OpenELIS Integration**
2. Check product categories - must be `Services/Lab/Test` or `Services/Lab/Panel`
3. Verify OpenELIS API URL is correct
4. Check Odoo logs for API errors
5. Verify OpenELIS endpoint is accessible: `/rest/odoo/test-order`

## Expected Behavior Summary

| Action | Expected Result |
|--------|----------------|
| Create customer (no ref) | Patient ID auto-generated (e.g., `P000001`) |
| Create customer (with ref) | Manual ref preserved, no auto-generation |
| Create second customer | Next patient ID generated (e.g., `P000002`) |
| Search by patient ID | Customer found in search results |
| Confirm test order | Order synced to OpenELIS with patient ID |
| Patient in OpenELIS | Patient created with ST identifier = patient ID |

## Next Steps

After successful testing:

1. **Configure Production Settings**:
   - Set appropriate OpenELIS API URL
   - Configure authentication if required
   - Set sequence starting number if needed

2. **Train Users**:
   - Explain that patient IDs are auto-generated
   - Show how to search by patient ID
   - Explain the sync process

3. **Monitor Sync**:
   - Check Odoo logs regularly
   - Monitor OpenELIS for synced patients
   - Verify data accuracy
