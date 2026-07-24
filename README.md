# IMS Catalog Module

## Overview

The **Catalog Module** is the central repository of all inventory items within the Inventory Management System (IMS). It enables users to browse, search, classify, and manage product master data while providing complete visibility into item specifications, purchasing information, suppliers, pricing, warehouse locations, and inventory attributes.

The module acts as the foundation for procurement, inventory planning, warehouse operations, purchasing, and reporting.

---

# Objectives

- Maintain a centralized Item Master.
- Provide detailed product information.
- Organize inventory through classifications.
- Maintain supplier and purchase information.
- Store pricing and warehouse location details.
- Support purchasing and inventory operations.

---

# Features

## Inventory Master Index

The Inventory screen provides a centralized listing of all catalog items.

Users can:

- Search items instantly
- Filter by warehouse
- View inventory quantities
- Review reorder information
- Open complete item details

---

## Search

Supports real-time searching using:

- Item Code
- Description
- Keywords

---

## Warehouse Filter

Users can isolate inventory for a specific warehouse using the **Warehouse (Bodega)** selector.

---

## Item Details

Selecting an item opens the complete Item Master profile.

Each item contains multiple information tabs.

---

# Item Master Structure

## 1. General Information

Contains the core master information.

Includes:

- Item Code
- Description
- Status
- Unit of Measure
- Dimensions
- Weight
- Corporate Code
- Purchase Type
- Tax Configuration
- Additional Item Attributes

Purpose:

Stores the primary identification and configuration of an inventory item.

---

## 2. Classification

Organizes products into business categories.

Contains:

- Category
- Family
- Brand
- Product Labels
- Classification Groups

Purpose:

Provides structured grouping for reporting, purchasing, and inventory analysis.

---

## 3. Purchase Information

Maintains purchasing-related information.

Includes:

### General Purchase Details

- Tax Percentage
- Tax Description
- Corporate Code
- Purchase Type

### Latest Quotation

Stores the most recent supplier quotation including:

- Supplier
- Currency
- Purchase Price
- Quotation Date

Purpose:

Supports procurement decisions using the latest supplier pricing information.

---

## 4. Supplier Information

Stores vendor-related information.

Includes:

- Primary Supplier
- Alternate Suppliers
- Vendor Details
- Lead Time
- Supplier References

Purpose:

Supports purchasing and vendor management.

---

## 5. Pricing

Maintains selling and purchasing prices.

May include:

- Standard Price
- Purchase Price
- Tier Pricing
- Price Configuration

Purpose:

Centralized pricing management.

---

## 6. Warehouse Location

Maintains physical storage locations.

Includes:

- Warehouse
- Shelf
- Bin
- Rack
- Storage Location

Purpose:

Helps warehouse teams quickly locate inventory.

---

## 7. Additional Information

Stores miscellaneous configuration.

Examples include:

- Custom Settings
- Additional Parameters
- Internal Configuration
- Business-specific attributes

---
