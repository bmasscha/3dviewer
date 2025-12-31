import glm

class Camera:
    def __init__(self, position=(0.0, 0.0, 3.0), fov=45.0, target=(0.0, 0.0, 0.0)):
        self.target = glm.vec3(target)
        self.fov = fov
        
        # Arcball parameters
        self.radius = 3.0
        self.sensitivity = 3.0 # Not really needed if 1:1 mapping
        self.zoom_sensitivity = 0.1
        
        # Orientation stored as quaternion (Identity initially)
        self.orientation = glm.quat()
        
        # Initialize position based on simplified start
        self.update_camera_vectors()

    def get_view_matrix(self):
        # View matrix is inverse of Camera World Matrix
        # Camera World Matrix: Translation(Pos) * Rotation(Orientation)
        # So View = inv(Rot) * inv(Trans)
        
        # Construct rotation matrix from quaternion
        R = glm.mat4_cast(self.orientation)
        # Translation
        T = glm.translate(glm.mat4(1.0), -self.position)
        
        # View = R^T * T (since R is orthogonal, inv(R) = R^T)
        # Actually glm.mat4_cast gives the rotation itself.
        # If orientation represents the camera's rotation in world space:
        # We need the View Matrix, which transforms World -> Camera.
        
        # Easier: Use lookAt with up-vector derived from orientation?
        # Or construct directly.
        
        # Let's derive Up and Pos from orientation.
        # Camera is at (0,0, radius) in View Space.
        # Rotated by Orientation.
        # Position = Target + Orientation * (0, 0, Radius)
        
        return glm.lookAt(self.position, self.target, self.get_up())

    def get_projection_matrix(self, aspect_ratio):
        return glm.perspective(glm.radians(self.fov), aspect_ratio, 0.1, 100.0)

    def project_to_sphere(self, x, y):
        """
        Projects x,y in range [-1, 1] onto a sphere of radius 1/sqrt(2) (or similar).
        Holroyd's trackball approach:
        If r <= 1/sqrt(2), z = sqrt(1 - r^2)
        Else, z = 1 / (2*r)  (Hyperbolic sheet)
        
        Simple Arcball:
        z^2 = 1 - x^2 - y^2
        """
        d = x*x + y*y
        r = 1.0
        if d < r * r * 0.5:
            # Inside sphere
            z = glm.sqrt(r*r - d)
        else:
            # On hyperbola
            z = (r*r*0.5) / glm.sqrt(d)
        
        return glm.normalize(glm.vec3(x, y, z))

    def rotate(self, prev_ndc_x, prev_ndc_y, curr_ndc_x, curr_ndc_y):
        """
        Applies rotation based on drag from prev_ndc to curr_ndc.
        Coords must be in [-1, 1] range.
        """
        if prev_ndc_x == curr_ndc_x and prev_ndc_y == curr_ndc_y:
            return

        p0 = self.project_to_sphere(prev_ndc_x, prev_ndc_y)
        p1 = self.project_to_sphere(curr_ndc_x, curr_ndc_y)
        
        # Axis of rotation = cross(p0, p1)
        axis = glm.cross(p0, p1)
        
        # Angle = acos(dot(p0, p1))
        # Be careful with precision
        d = glm.clamp(glm.dot(p0, p1), -1.0, 1.0)
        angle = glm.acos(d) * self.sensitivity
        
        if glm.length(axis) > 0.0001:
            axis = glm.normalize(axis)
            # Create rotation quaternion
            # Note: We rotate the CAMERA around the target.
            q_rot = glm.angleAxis(angle, axis)
            
            # Update orientation
            # To orbit "around" the object, we apply rotation relative to current view?
            # Standard Arcball: q_new = q_drag * q_old
            # Usually: q_rot is in View Space (screen space drag).
            # So we apply it "locally" to the camera's orientation.
            
            # This order rotates the camera in its own frame
            self.orientation = glm.normalize(self.orientation * glm.inverse(q_rot))
            self.update_camera_vectors()

    def process_scroll(self, yoffset):
        self.radius -= (float(yoffset) * self.zoom_sensitivity)
        if self.radius < 0.1:
            self.radius = 0.1
        if self.radius > 20.0:
            self.radius = 20.0
        self.update_camera_vectors()

    def pan(self, dx, dy):
        """
        Translates the camera target and position along the camera's local right and up vectors.
        dx, dy are change in NDC coordinates.
        """
        # Calculate local axes from orientation
        # Right: Orientation * (1, 0, 0)
        # Up: Orientation * (0, 1, 0)
        right = self.orientation * glm.vec3(1.0, 0.0, 0.0)
        up = self.get_up()
        
        # Scale movement by radius so object follows mouse at target depth
        # Arcball usually means we are looking at something at 'target'
        # Scale factor is empirical, but radius/2 is often good for NDC [-1, 1]
        scale = self.radius * 0.5
        
        delta = (right * -dx * scale) + (up * -dy * scale)
        
        self.target += delta
        self.position += delta
        # update_camera_vectors is not strictly needed if we update position directly,
        # but good for consistency. 
        # Actually, self.position = self.target + pos_offset in update_camera_vectors.
        # So we just update target, and then call update_camera_vectors.
    
    def update_camera_vectors(self):
        # Position is defined by orientation and radius
        # View direction in local space is (0, 0, -1)
        # Position in local space is (0, 0, radius) potentially?
        # Let's say: Camera is at (0, 0, radius) relative to target, then rotated.
        
        view_vec = glm.vec3(0.0, 0.0, 1.0) # From target to camera
        
        pos_offset = self.orientation * view_vec * self.radius
        self.position = self.target + pos_offset

    def get_up(self):
        return self.orientation * glm.vec3(0.0, 1.0, 0.0)
