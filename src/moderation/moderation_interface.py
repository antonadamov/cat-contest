from abc import ABC, abstractmethod

class ImageModerationService(ABC):

    @abstractmethod
    def moderate_image(self, image_path):
        pass