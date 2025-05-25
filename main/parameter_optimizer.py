from typing import Dict, Any, List
import numpy as np
from scipy.optimize import minimize
from .avatar_parameters import AvatarParameters
from .error_handling import ParameterError

class ParameterOptimizer:
    """Optimize avatar parameters for better performance"""
    
    def __init__(self, parameters: AvatarParameters):
        """Initialize optimizer with avatar parameters"""
        self.parameters = parameters
        self.bounds = self._calculate_bounds()
    
    def _calculate_bounds(self) -> List[tuple]:
        """Calculate parameter bounds"""
        bounds = []
        for param in self.parameters:
            min_val = param.get('min', -100)
            max_val = param.get('max', 100)
            bounds.append((min_val, max_val))
        return bounds
    
    def objective_function(self, x: np.ndarray) -> float:
        """Objective function to minimize"""
        # Example objective: minimize parameter variance
        return np.var(x)
    
    def optimize(self) -> Dict[str, Any]:
        """Optimize parameters"""
        try:
            # Convert parameters to numpy array
            initial_params = np.array([param['value'] for param in self.parameters])
            
            # Perform optimization
            result = minimize(
                self.objective_function,
                initial_params,
                bounds=self.bounds,
                method='L-BFGS-B'
            )
            
            if not result.success:
                raise ParameterError("Optimization failed: " + result.message)
            
            # Update optimized parameters
            optimized_params = []
            for i, param in enumerate(self.parameters):
                param['value'] = float(result.x[i])
                optimized_params.append(param)
            
            return {
                'success': True,
                'optimized_parameters': optimized_params,
                'message': "Optimization successful",
                'performance_gain': self._calculate_performance_gain(result.x)
            }
            
        except Exception as e:
            raise ParameterError(f"Optimization failed: {str(e)}")
    
    def _calculate_performance_gain(self, optimized_values: np.ndarray) -> float:
        """Calculate performance gain from optimization"""
        initial_values = np.array([param['value'] for param in self.parameters])
        initial_variance = np.var(initial_values)
        optimized_variance = np.var(optimized_values)
        return (initial_variance - optimized_variance) / initial_variance * 100
