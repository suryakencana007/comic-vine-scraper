'''
This module is home to the FinishForm class.

@author: Cory Banack
'''

import clr
import resources
import i18n
from cvform import CVForm 

clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import AutoScaleMode, Button, DialogResult, Label

clr.AddReference('System.Drawing')
from System.Drawing import ContentAlignment, Point, Size

# =============================================================================
class FinishForm(CVForm):
   '''
   This is the last modal popup dialog that you see when you run the scraper.
   It lets you know how many books were scraped, and how many were skipped.
   '''
   
   #===========================================================================
   def __init__(self, scraper, status):
      '''
      Initializes this form.
      
      'scraper' -> the ScrapeEngine that we are running as part of.
      'status' -> a list containing two integers, the first is the number of 
                 books that were scraped and the second is the number that were
                 skipped (both reported to the user by this form)
      '''
      
      CVForm.__init__(self, scraper.comicrack.MainWindow, "finishformLocation")
      self.__build_gui( status[0], status[1] )

      
   # ==========================================================================
   def __build_gui(self, scraped_n, skipped_n):
      '''
       Constructs and initializes the gui for this form.
      'scraped_n' -> the number of books that were scraped (reported to user)
      'skipped_n' -> the number of books that were skipped (reported to user)
      '''
      
      # 1. --- build each gui component
      scrape_label = self.__build_scrape_label(scraped_n)
      skip_label = self.__build_skip_label(skipped_n)
      ok = self.__build_okbutton()
   
      # 2. --- configure this form, and add all the gui components to it
      self.AcceptButton = ok
      self.AutoScaleMode = AutoScaleMode.Font
      self.Text = 'Comic Vine Scraper - v' + resources.SCRIPT_VERSION
      self.ClientSize = Size(300, 90)
   
      self.Controls.Add(scrape_label)
      self.Controls.Add(skip_label)
      self.Controls.Add(ok)
      
      # 3. --- define the keyboard focus tab traversal ordering
      ok.TabIndex = 0
      
   # ==========================================================================
   def __build_scrape_label(self, scraped_n):
      ''' 
      Builds and returns the 'number scraped' Label for this form.
      'scraped_n' -> the number of books that were scraped. 
      '''

      label = Label()
      label.Location = Point(10, 10)
      label.Size = Size(280, 13)
      label.TextAlign = ContentAlignment.MiddleCenter
      label.Text = "Scraped details for {0} comic book{1}."\
         .format(scraped_n, "" if scraped_n==1 else "s") 
      return label

   
   # ==========================================================================
   def __build_skip_label(self, skipped_n):
      ''' 
      Builds and returns the 'number skipped' Label for this form.
      'skipped_n' -> the number of books that were skipped. 
      '''

      label = Label()
      label.Location = Point(10, 30) 
      label.Size = Size(280, 13)
      label.TextAlign = ContentAlignment.MiddleCenter
      label.Text = "Skipped {0} comic book{1}."\
         .format(skipped_n, "" if skipped_n==1 else "s") 
      return label
   
   # ==========================================================================
   def __build_okbutton(self):
      ''' Builds and returns the ok button for this form. '''

      button = Button()
      button.DialogResult = DialogResult.OK
      button.Location = Point(120, 58)
      button.Size = Size(60, 23)
      button.Text = i18n.get("MessageBoxOk")
      button.UseVisualStyleBackColor = True
      return button

      
   # ==========================================================================
   def show_form(self):
      ''' Displays this form, blocking until the user closes it. '''  
      self.ShowDialog() # blocks
      return None