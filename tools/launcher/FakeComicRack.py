'''
This module contains the FakeComicRack class, which is a special class that 
pretends to be the real ComicRack object. 

ComicVineScraper REQUIRES a ComicRack object in order to run; either the "real"
one if it is available (i.e. we're running as a plugin) or this fake one if 
we are running as a standalone application or in a development IDE.
'''

import clr
clr.AddReferenceByPartialName("System.Windows.Forms")
from System.Windows.Forms import Form

#==============================================================================
class FakeComicRack(object):
   ''' A static class that emulates the real ComicRack object. '''
   class AppImpl:
      ProductVersion = '999.999.99999'
      def GetComicPage(self, arg1, arg2):
            return None
      def SetCustomBookThumbnail(self, book, bitmap):
         return True
   
   class MainForm(Form):
      pass
   
   @classmethod
   def Localize(cls, resource, key, backuptext):
      return backuptext   
   
   App = AppImpl()
   MainWindow = MainForm()