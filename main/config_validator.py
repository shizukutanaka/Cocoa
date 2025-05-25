import json
import os
from typing import Dict, Any, List, Optional
from .error_handling import ConfigError
from .logging_manager import Logger

class ConfigValidator:
    """Validate configuration files"""
    
    def __init__(self, logger: Logger, schema_path: str = "config/schema.json"):
        """Initialize validator"""
        self.logger = logger
        self.schema = self._load_schema(schema_path)
        
    def _load_schema(self, schema_path: str) -> Dict[str, Any]:
        """Load validation schema"""
        try:
            if not os.path.exists(schema_path):
                raise ConfigError(f"Schema file not found: {schema_path}")
                
            with open(schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"Error loading schema: {str(e)}")
            raise ConfigError(f"Failed to load schema: {str(e)}")
    
    def validate(self, config_path: str) -> Dict[str, Any]:
        """Validate a configuration file"""
        try:
            if not os.path.exists(config_path):
                raise ConfigError(f"Configuration file not found: {config_path}")
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            return self._validate_config(config)
            
        except Exception as e:
            self.logger.error(f"Error validating configuration: {str(e)}")
            raise ConfigError(f"Failed to validate configuration: {str(e)}")
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration against schema"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Validate required fields
        missing_fields = []
        for field in self.schema.get('required', []):
            if field not in config:
                missing_fields.append(field)
                validation_result['valid'] = False
                validation_result['errors'].append(f"Missing required field: {field}")
        
        # Validate field types
        for field, value in config.items():
            field_schema = self.schema.get('fields', {}).get(field)
            if field_schema:
                if not self._validate_type(value, field_schema.get('type')):
                    validation_result['valid'] = False
                    validation_result['errors'].append(
                        f"Invalid type for {field}: expected {field_schema['type']}")
                    
                # Validate constraints
                if not self._validate_constraints(value, field_schema.get('constraints', {})):
                    validation_result['valid'] = False
                    validation_result['errors'].append(
                        f"Constraints failed for {field}")
                    
        # Validate relationships between fields
        if not self._validate_relationships(config):
            validation_result['valid'] = False
            validation_result['errors'].append("Field relationships validation failed")
            
        return validation_result
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type"""
        type_map = {
            'string': str,
            'number': (int, float),
            'boolean': bool,
            'object': dict,
            'array': list
        }
        
        expected_types = type_map.get(expected_type)
        if expected_types:
            return isinstance(value, expected_types)
        return True
    
    def _validate_constraints(self, value: Any, constraints: Dict[str, Any]) -> bool:
        """Validate value constraints"""
        for constraint, constraint_value in constraints.items():
            if constraint == 'min':
                if value < constraint_value:
                    return False
            elif constraint == 'max':
                if value > constraint_value:
                    return False
            elif constraint == 'pattern':
                import re
                if not re.match(constraint_value, str(value)):
                    return False
        return True
    
    def _validate_relationships(self, config: Dict[str, Any]) -> bool:
        """Validate relationships between fields"""
        relationships = self.schema.get('relationships', [])
        for relationship in relationships:
            field1 = config.get(relationship['field1'])
            field2 = config.get(relationship['field2'])
            
            if relationship['type'] == 'equals':
                if field1 != field2:
                    return False
            elif relationship['type'] == 'greater_than':
                if field1 <= field2:
                    return False
            elif relationship['type'] == 'less_than':
                if field1 >= field2:
                    return False
        return True
