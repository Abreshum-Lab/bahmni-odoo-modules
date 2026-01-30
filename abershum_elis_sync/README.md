# Abershum ELIS Sync Module

This Odoo module provides integration between Odoo and OpenELIS for syncing lab test orders and patient data.

## Features

### 1. Patient ID Generation
- **Automatic Patient ID Generation**: When a new customer/patient is created in Odoo, a unique patient ID is automatically generated using a sequence
- **Format**: `P000001`, `P000002`, etc. (configurable prefix and padding)
- **Storage**: Patient ID is stored in the `ref` field of the customer record
- **Uniqueness**: The `ref` field has a unique constraint to ensure no duplicate patient IDs

### 2. Test Order Sync
- **Automatic Sync**: When a sale order containing lab test products is confirmed, it automatically syncs to OpenELIS
- **Product Filtering**: Only products in `Services/Lab/Test` or `Services/Lab/Panel` categories are synced
- **REST API Integration**: Uses OpenELIS REST API endpoint `/rest/odoo/test-order`

### 3. Patient Data Mapping
- **Patient Identifier**: Odoo partner `ref` field maps to OpenELIS patient identifier (ST type)
- **Patient UUID**: Odoo partner `uuid` field maps to OpenELIS patient UUID
- **Patient Information**: Name, phone, and email are synced to OpenELIS

## Installation

1. Copy the `abershum-elis-sync` module to your Odoo addons path
2. Update the module list in Odoo
3. Install the module: **Apps** → Search "Abershum ELIS Sync" → **Install**

## Configuration

### 1. OpenELIS API Settings

Go to **Settings** → **OpenELIS Integration** and configure:

- **Enable OpenELIS Test Order Sync**: Enable/disable automatic sync of test orders
- **Enable Patient Sync to OpenELIS**: Enable/disable automatic sync of patient data (optional)
- **OpenELIS API URL**: Base URL for OpenELIS REST API (e.g., `http://openelis:8080/openelis`)
- **OpenELIS API Username**: Username for API authentication (optional)
- **OpenELIS API Password**: Password for API authentication (optional)

### 2. Patient ID Sequence

The patient ID sequence is automatically created when the module is installed:
- **Sequence Code**: `abershum.patient.id.sequence`
- **Default Prefix**: `P`
- **Default Padding**: 6 digits
- **Format**: `P000001`, `P000002`, etc.

To customize the sequence:
1. Go to **Settings** → **Technical** → **Sequences & Identifiers** → **Sequences**
2. Search for "Patient ID Sequence"
3. Edit the prefix, padding, or starting number as needed

## Usage

### Creating a New Patient/Customer

1. Go to **Sales** → **Customers** → **Create**
2. Fill in customer details (name, phone, email, etc.)
3. **Patient ID is automatically generated** and stored in the **Internal Reference** (`ref`) field
4. The patient ID will be displayed as `[P000001]` next to the customer name

### Creating a Test Order

1. Create a **Sale Order** with a customer that has a patient ID (`ref` field)
2. Add products that belong to `Services/Lab/Test` or `Services/Lab/Panel` categories
3. **Confirm** the sale order
4. The test order is automatically synced to OpenELIS (if sync is enabled)

### Testing Patient Creation

To test patient creation:

1. **Create a new customer**:
   - Go to **Sales** → **Customers** → **Create**
   - Enter customer name: "John Doe"
   - Enter phone: "1234567890"
   - Enter email: "john@example.com"
   - **Save** the customer
   - **Verify**: Check that the `ref` field is automatically populated with a patient ID (e.g., `P000001`)

2. **Verify Patient ID**:
   - The patient ID should be visible in the customer form
   - Search for the customer using the patient ID
   - The patient ID should be unique

3. **Check OpenELIS**:
   - When a test order is created with this customer, the patient ID will be synced to OpenELIS
   - OpenELIS will use this patient ID (ref field) as the ST identifier type

## Data Mapping

### Patient Mapping (Odoo → OpenELIS)

| Odoo Field | OpenELIS Field | Description |
|------------|----------------|-------------|
| `ref` | Patient Identity (ST) | Patient identifier |
| `uuid` | Patient UUID | Unique patient identifier |
| `name` | Person Name | Patient full name |
| `phone` | Person Phone | Contact phone number |
| `email` | Person Email | Contact email address |

### Test Order Mapping (Odoo → OpenELIS)

| Odoo Field | OpenELIS Field | Description |
|------------|----------------|-------------|
| `sale_order.id` | Sample UUID | Unique sample identifier |
| `sale_order.name` | Sample Accession Number | Order reference |
| `sale_order.date_order` | Sample Entry Date | Order date |
| `order_line.product_uuid` | Test/Panel ID | Mapped via external_reference table |
| `order_line.product_uom_qty` | Quantity | Test quantity |

## API Endpoints

### OpenELIS Endpoints

- **Test Order Sync**: `POST /rest/odoo/test-order`
  - Receives test order data from Odoo
  - Creates/updates patient if needed
  - Creates sample and analysis records

### Odoo Integration Points

- **Sale Order Confirmation**: Automatically triggers sync when order is confirmed
- **Customer Creation**: Automatically generates patient ID
- **Customer Update**: Can sync patient updates to OpenELIS (if enabled)

## Troubleshooting

### Patient ID Not Generated

1. Check that the sequence exists: **Settings** → **Technical** → **Sequences & Identifiers** → **Sequences**
2. Verify the sequence code: `abershum.patient.id.sequence`
3. Check Odoo logs for errors

### Test Order Not Syncing

1. Verify sync is enabled in **Settings** → **OpenELIS Integration**
2. Check that products are in correct categories (`Services/Lab/Test` or `Services/Lab/Panel`)
3. Verify OpenELIS API URL is correct
4. Check Odoo logs for API errors
5. Verify OpenELIS endpoint is accessible

### Patient Not Found in OpenELIS

1. Patient is created in OpenELIS when the first test order is synced
2. Verify patient has a `ref` field (patient ID)
3. Check OpenELIS logs for patient creation errors

## Development

### Module Structure

```
abershum-elis-sync/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── openelis_sync_service.py    # Test order sync service
│   ├── res_partner.py               # Patient ID generation
│   ├── res_config_settings.py       # Configuration settings
│   └── sale_order.py                # Sale order hook
├── views/
│   └── res_config_settings_view.xml # Settings UI
├── data/
│   └── ir_sequence_data.xml         # Patient ID sequence
├── security/
│   └── ir.model.access.csv          # Access rights
└── README.md
```

### Key Components

1. **res_partner.py**: Extends `res.partner` to auto-generate patient IDs
2. **openelis_sync_service.py**: Handles test order sync to OpenELIS
3. **sale_order.py**: Hooks into sale order confirmation to trigger sync
4. **ir_sequence_data.xml**: Defines patient ID sequence

## License

LGPL-3
