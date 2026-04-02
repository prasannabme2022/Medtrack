"""
Local file-based storage fallback for when AWS credentials are not available.
This ensures data persists across server restarts during local development.
"""
import json
import os
from datetime import datetime

class LocalStorage:
    """Simple JSON file-based storage that mimics DynamoDB Table interface"""
    
    def __init__(self, table_name):
        self.table_name = table_name
        self.storage_dir = os.path.join(os.path.dirname(__file__), 'local_data')
        self.file_path = os.path.join(self.storage_dir, f'{table_name}.json')
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Load existing data or create empty storage
        self.data = self._load()
    
    def _load(self):
        """Load data from JSON file"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Support both list format and dict format (keyed by primary key)
                    if isinstance(loaded, dict):
                        return list(loaded.values())
                    return loaded
            except Exception as e:
                print(f"Warning: Could not load {self.table_name}: {e}")
                return []
        return []
    
    def _save(self):
        """Save data to JSON file"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving {self.table_name}: {e}")
    
    def put_item(self, Item):
        """Add or update an item"""
        # Remove existing item with same key if it exists
        key_name = self._get_key_name()
        key_value = Item.get(key_name)
        
        self.data = [item for item in self.data if item.get(key_name) != key_value]
        self.data.append(Item)
        self._save()
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}
    
    def get_item(self, Key):
        """Get a single item by key"""
        key_name = list(Key.keys())[0]
        key_value = Key[key_name]
        
        for item in self.data:
            if item.get(key_name) == key_value:
                return {'Item': item}
        return {}
    
    def scan(self, FilterExpression=None, ExpressionAttributeValues=None, **kwargs):
        """Scan all items with optional filtering"""
        items = self.data.copy()
        
        # Simple filter implementation
        if FilterExpression and ExpressionAttributeValues:
            # Parse simple equality filters like "status = :status"
            if '=' in FilterExpression:
                parts = FilterExpression.split('=')
                field = parts[0].strip()
                value_key = parts[1].strip()
                
                if value_key in ExpressionAttributeValues:
                    filter_value = ExpressionAttributeValues[value_key]
                    items = [item for item in items if item.get(field) == filter_value]
        
        return {'Items': items, 'Count': len(items)}
    
    def query(self, KeyConditionExpression=None, FilterExpression=None, 
              ExpressionAttributeValues=None, **kwargs):
        """Query items (simplified - just returns filtered scan)"""
        return self.scan(FilterExpression=FilterExpression, 
                        ExpressionAttributeValues=ExpressionAttributeValues)
    
    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues=None, 
                    ExpressionAttributeNames=None, **kwargs):
        """Update an existing item"""
        key_name = list(Key.keys())[0]
        key_value = Key[key_name]
        
        for item in self.data:
            if item.get(key_name) == key_value:
                # Parse SET expressions
                if UpdateExpression and UpdateExpression.startswith('SET'):
                    updates = UpdateExpression.replace('SET ', '').split(',')
                    
                    for update in updates:
                        update = update.strip()
                        if '=' in update:
                            parts = update.split('=')
                            field = parts[0].strip()
                            value_ref = parts[1].strip()
                            
                            # Handle attribute name aliases
                            if ExpressionAttributeNames and field in ExpressionAttributeNames:
                                field = ExpressionAttributeNames[field]
                            
                            # Handle attribute value references
                            if ExpressionAttributeValues and value_ref in ExpressionAttributeValues:
                                item[field] = ExpressionAttributeValues[value_ref]
                
                self._save()
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
        
        return {}
    
    def delete_item(self, Key):
        """Delete an item"""
        key_name = list(Key.keys())[0]
        key_value = Key[key_name]
        
        self.data = [item for item in self.data if item.get(key_name) != key_value]
        self._save()
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}
    
    def _get_key_name(self):
        """Get the primary key name for this table"""
        # Map table names to their keys
        key_map = {
            'medtrack_patients': 'email',
            'medtrack_doctors': 'email',
            'medtrack_appointments': 'appointment_id',
            'medtrack_medical_vault': 'vault_id',
            'medtrack_blood_bank': 'blood_group',
            'medtrack_invoices': 'invoice_id',
            'medtrack_chat_messages': 'message_id',
            'medtrack_mood_logs': 'mood_id',
            'medtrack_appointment_requests': 'request_id',
            'MedTrack_Predictions': 'patient_id'
        }
        return key_map.get(self.table_name, 'id')
