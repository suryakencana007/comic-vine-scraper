'''
This module contains the PersistentForm class.

@author: Cory Banack
'''
#corylow: comment and cleanup this file
# coryhigh: externalize
import clr
import log
from utils import sstr, load_map, persist_map
import resources

clr.AddReference('System')
from System.Threading import Thread, ThreadStart

clr.AddReference('System.Drawing')
from System.Drawing import Point, Rectangle, Size

clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import Form, FormStartPosition, Screen

#==============================================================================
class PersistentForm(Form):
   '''
   A superclass of all the forms in the Comic Vine Scraper.  It is responsible
   for implementing persistence (i.e. save/restore between runs of the app) of
   each form's location and size.  All data is stored and read from the 
   geometry settings file.  
   
   Subclasses indicate which attributes (location, size) should be persisted 
   by passing specific arguments into the constructor.
   '''
   
   
   #===========================================================================
   def __init__(self, persist_loc_key_s = None, persist_size_key_s = None):
      '''
      Constructs a new PersistentForm.
      
      If persist_loc_key_s is specified, this form will attempt to save and
      restore its previous location every time it is run.  If no previous is
      available, or if this parameter is None, then the form will be centered on
      it's parent via Form.CenterToParent().
      
      If persist_size_key_s is specified, this form will attempt to save and 
      restore its previous size every time it is run (a feature which only makes
      sense if the form is resizable!).  If no previous is available, or if this
      parameter is None, the form will use its natural size (i.e. no change)
      
      Note that both of these parameters should be unique, as they are also 
      used as KEYS to the saved values that they represent in the geometry
      settings file! 
      '''

      super(PersistentForm, self).__init__()
      
      # whether or not the user has moved or resized this form.
      self._bounds_changed = False
      
      # the pref key for persisting this form's location, or None to skip
      self._persist_loc_key_s = persist_loc_key_s

      # the pref key for persisting this form's size, or None to skip
      self._persist_size_key_s = persist_size_key_s
      
      self._initialize()



   #===========================================================================
   def _initialize(self):
      ''' intial configuration for new instances of this class '''
      
      Form.__init__(self)
      self.StartPosition = FormStartPosition.Manual
      self.Load += self._install_persistent_bounds
      

      
   #===========================================================================
   def _install_persistent_bounds(self, a, b):
      """
      Called when this Form is just about to be displayed.  This method tries to
      restore the previously used location/size settings, and it also checks
      them to make sure that they are still valid on the current monitor 
      configuration (and fixes them if they are not!)
      """
      
      self._load_bounds()
      
      # compute the center of our current bounding rectangle
      b = self.Bounds
      center = Point(b.X+b.Width/2, b.Y+b.Height/2)
      
      # if the center of this window is not onscreen, make it so that it is
      screens = Screen.AllScreens
      screen_bounds = screens[0].Bounds
      for screen in screens:
         screen_bounds = Rectangle.Union(screen_bounds, screen.Bounds)
      if not screen_bounds.Contains(center):
         log.debug("WARNING: form's location was offscreen; adjusted it")
         self.CenterToScreen()
         self._bounds_changed = True
      else:
         self._bounds_changed = False
   

   
   #===========================================================================   
   def _load_bounds(self):
      """
      Attempts to load the persisted size/location details from the geometry
      settings files, and adjust the form's current state to match.
      """
      
      do_default_loc = True
      if self._persist_size_key_s or self._persist_loc_key_s:
         prefs = load_map(resources.GEOMETRY_FILE)
         
         # grab the stored size value, if any, and apply it
         if self._persist_size_key_s and self._persist_size_key_s in prefs:
            try:
               size = prefs[self._persist_size_key_s].split(',')
               self.Size = Size(int(size[0]), int(size[1]))
            except:
               # didn't work, just stick with the forms current size
               pass
            
         # grab the stored location value, if any, and apply it
         if self._persist_loc_key_s and self._persist_loc_key_s in prefs:
            try:
               loc = prefs[self._persist_loc_key_s].split(',')
               loc = Point(int(loc[0]), int(loc[1]))
               self.Location = loc
               do_default_loc = False
            except:
               do_default_loc = True
      
      if do_default_loc:
         self.CenterToParent()          
   

   
   #===========================================================================
   def _save_bounds(self):
      """
      Attempts to store this form's current size/location details into the 
      geometry settings file.
      """
      
      # might as well use an off thread, makes the gui a bit more responsive
      log.debug("saved window geometry: ", self._persist_loc_key_s, 
                " ", self._persist_size_key_s )
      
      def delegate():
         if self._persist_size_key_s or self._persist_loc_key_s:
            prefs = load_map(resources.GEOMETRY_FILE)
            if self._persist_loc_key_s:
               prefs[self._persist_loc_key_s] =\
                  sstr(self.Location.X) + "," + sstr(self.Location.Y)
            if self._persist_size_key_s:
               prefs[self._persist_size_key_s] =\
                  sstr(self.Width) + "," + sstr(self.Height)
            persist_map(prefs, resources.GEOMETRY_FILE)
      Thread(ThreadStart(delegate)).Start()
      
      
   #===========================================================================
   def OnMove(self, args):
      # Overridden to record that the location of this form has changed
      Form.OnMove(self, args)
      self._bounds_changed = True


   #===========================================================================
   def OnResize(self, args):
      # Overridden to record that the size of this form has changed
      Form.OnResize(self, args)
      self._bounds_changed = True


   #===========================================================================
   def OnFormClosing(self, args):
      # Overridden to make sure that we write out our persistent size/location
      # changes (if there were any) and do any other cleanup needed before 
      # shutting down this window.
      if self._bounds_changed:
         self._save_bounds()
      self.Load -= self._install_persistent_bounds
      Form.OnFormClosing(self, args)
      
   