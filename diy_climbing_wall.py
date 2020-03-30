#!/usr/bin/env python
# coding: utf-8

from OCC.Display.SimpleGui import init_display

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeHalfSpace
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_MakeFace
from OCC.Core.BRepFeat import BRepFeat_MakeCylindricalHole
from OCC.Core.gp import gp_Ax1, gp_Pnt, gp_Dir, gp_Trsf, gp_Vec, gp_XYZ, gp_Pln

from math import radians, sin, cos


def euler_to_gp_trsf(euler_zxz=None, unit="deg"):
    
    if euler_zxz is None:
        euler_zxz = [0, 0, 0]
    if unit == "deg":  # convert angle to radians
        euler_zxz = [radians(a) for a in euler_zxz]
    
    x = gp_Ax1(gp_Pnt(), gp_Dir(1, 0, 0))
    z = gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1))

    trns = gp_Trsf()
    trns.SetRotation(z, euler_zxz[2])

    trns_next = gp_Trsf()
    trns_next.SetRotation(x, euler_zxz[1])

    trns = trns*trns_next

    trns_next = gp_Trsf()
    trns_next.SetRotation(z, euler_zxz[0])

    return trns*trns_next


class Part:

    def __init__(self, pos=None, ori=None, parent=None):
        if ori is None:
            ori = [0, 0, 0]
        if pos is None:
            pos = [0, 0, 0]
        self._position = pos
        self._orientation = ori
        self._parent = parent
        self._shape = None
        self._trans = None

    def place(self):

        assert(self._shape is not None)

        if self._parent is not None:
            trans = self._parent._trans
        else:
            trans = gp_Trsf()

        translation = gp_Trsf()
        translation.SetTranslation(gp_Vec(*self._position))
        trans = trans * translation

        rot = euler_to_gp_trsf(self._orientation)
        trans = trans * rot

        brep_trns = BRepBuilderAPI_Transform(self._shape, trans, False)
        brep_trns.Build()
        self._trans = trans
        self._shape = brep_trns.Shape()

    @property
    def position(self):
        """
        returns the position in global coordinates
        """
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self.place()

    @property
    def orientation(self):
        """
        returns the orientation in local coordinates
        """
        return self._orientation

    @orientation.setter
    def orientation(self, value):
        self._orientation = value
        self.place()


class Bar(Part):

    def __init__(self,
                 pos=None,
                 ori=None,
                 parent=None,
                 length=2000.,
                 section=(80., 100.)):

        super().__init__(pos, ori, parent)
        self._length = length
        self._section = section

        self._shape = BRepPrimAPI_MakeBox(length, section[0], section[1]).Shape()
        self.place()
        

class Panel(Part):

    def __init__(self,
                 pos=None,
                 ori=None,
                 parent=None,
                 width=1000.,
                 height=2400.,
                 thickness=21.,
                 holes=None):
        super().__init__(pos, ori, parent)
        if holes is None:
            holes = {'x_start': 100,
                     'x_dist': 200,
                     'y_start': 100,
                     'y_dist': 200,
                     'diameter': 13}
        self._width = width
        self._height = height
        self._thickness = thickness
        self._holes = holes

        self._shape = BRepPrimAPI_MakeBox(self._height, self._width, self._thickness).Shape()
        x = self._holes['x_start']
        y = self._holes['y_start']
        while x < self._height:
            while y < self._width:
                feature_origin = gp_Ax1(gp_Pnt(x, y, 0), gp_Dir(0, 0, 1))
                feature_maker = BRepFeat_MakeCylindricalHole()
                feature_maker.Init(self._shape, feature_origin)
                feature_maker.Build()
                feature_maker.Perform(self._holes['diameter'] / 2.0)
                self._shape = feature_maker.Shape()
                y += self._holes['y_dist']
            x += self._holes['x_dist']
            y = self._holes['y_start']
        
        self.place()


def climbing_wall(wall_width=2000.,
                  wall_height=2400.,
                  wall_thickness=21.,
                  wall_angle=25.,
                  gap=100.,
                  safety=500.,
                  holes=None):
    """
    create a free standing climbing wall

    :param wall_width: the width of the climbable surface
    :param wall_height: the height of the climbable surface
    :param wall_thickness: the thickness of the plywood
    :param wall_angle: the angle of overhang
    :param gap: the desired gap between the top part of
           the climbable surface and the horizontal top bar
    :param safety: extra length of the left and right floor
           bars to prevent tilting
    :param holes: the holes dict for defining the panels
           of the climbable surface

    :return: a list of parts that make up the climbing wall
    """
    if holes is None:
        holes = {'x_start': 100.,
                 'x_dist': 200.,
                 'y_start': 100.,
                 'y_dist': 200.,
                 'diameter': 13.}

    # cross section of the bars for the rear construction
    bar_width = 100
    bar_height = 80
    bar_section = (bar_width, bar_height)

    parts =[]

    # some auxiliary variables
    ra = radians(wall_angle)
    sina = sin(ra)
    cosa = cos(ra)
    tana = sina/cosa

    # create horizontal bar on the left side
    l = bar_width + (wall_height + gap) * sina + safety
    horizontal_left = Bar(pos=[0, 0, 0],
                          ori=[0, 0, -90],
                          length=l,
                          section=bar_section)
    parts.append(horizontal_left)

    # create horizontal bar on the right side
    horizontal_right = Bar(pos=[wall_width + horizontal_left._section[0], 0, 0],
                           ori=[0, 0, -90],
                           length=l,
                           section=bar_section)
    parts.append(horizontal_right)

    # create horizontal part in the lower back
    back = Bar(pos=[horizontal_left._section[0], 0, bar_height],
               ori=[0, 0, 90],
               parent=horizontal_left,
               length=wall_width + 2*horizontal_left._section[0],
               section=bar_section)
    parts.append(back)


    # create the three diagonal bars
    dz = back._section[1] - back._section[0] * sina
    dy = back._section[0] * sina * tana
    l = wall_height + 2*bar_width/tana + gap
    diag1 = Bar(pos=[horizontal_left._section[0], dy, dz],
                ori=[-90, wall_angle-90, 0],
                parent=back,
                length=l,
                section=(bar_height, bar_width))
    parts.append(diag1)

    diag2 = Bar(pos=[0, (wall_width - horizontal_left._section[1])/2, 0],
                parent=diag1,
                length=l,
                section=(bar_height, bar_width))
    parts.append(diag2)

    diag3 = Bar(pos=[0, (wall_width - horizontal_left._section[1]) / 2, 0],
                parent=diag2,
                length=l,
                section=(bar_height, bar_width))
    parts.append(diag3)

    # cut diagonal bars at plane parallel to xy
    pnt = gp_Pnt(0, 0, 2 * bar_height)
    pln = gp_Pln(pnt, gp_Dir(0, 0, 1))
    face = BRepBuilderAPI_MakeFace(pln).Shape()
    tool1 = BRepPrimAPI_MakeHalfSpace(face, gp_Pnt(0, 0, 0)).Solid()

    # cut diagonal bars at plane parallel to xz
    pnt = gp_Pnt(0, -bar_width - (wall_height + gap)*sina, 0)
    pln = gp_Pln(pnt, gp_Dir(0, 1, 0))
    face = BRepBuilderAPI_MakeFace(pln).Shape()
    tool2 = BRepPrimAPI_MakeHalfSpace(face, gp_Pnt(0, pnt.Y()-1, 0)).Solid()
    for bar in [diag1, diag2, diag3]:
        bar._shape = BRepAlgoAPI_Cut(bar._shape, tool1).Shape()
        bar._shape = BRepAlgoAPI_Cut(bar._shape, tool2).Shape()

    # add the climbing panels
    panel_lo = Panel(pos=[tana*diag1._section[1], 0, -wall_thickness],
                     parent=diag1,
                     width=wall_width,
                     height=wall_height/2,
                     thickness=wall_thickness,
                     holes=holes)
    parts.append(panel_lo)

    panel_lo = Panel(pos=[panel_lo._height, 0, 0],
                     parent=panel_lo,
                     width=wall_width,
                     height=wall_height / 2,
                     thickness=wall_thickness,
                     holes=holes)
    parts.append(panel_lo)

    # add vertical bars
    front_section = (100, 100)
    dx = 2 * bar_width + (wall_height + gap) * sina
    dz = bar_height
    l = (wall_height + gap) * cosa + bar_height
    vertical_left = Bar(pos=[dx, 0, dz],
                        ori=[90, 90, -90],
                        length=l,
                        parent=horizontal_left,
                        section=front_section)
    parts.append(vertical_left)

    vertical_right = Bar(pos=[dx, 0, dz],
                         ori=[90, 90, -90],
                         length=l,
                         parent=horizontal_right,
                         section=front_section)
    parts.append(vertical_right)

    dx = bar_height + front_section[0] + (wall_height + gap) * cosa
    top = Bar(pos=[dx, 0, 0],
              ori=[90, 0, 0],
              length=wall_width + 2*bar_width,
              parent=vertical_left,
              section=front_section)
    parts.append(top)

    return parts


if __name__ == '__main__':

    wall = {'wall_width': 2000,
            'wall_height': 2400,
            'wall_thickness': 21,
            'wall_angle': 25,
            'gap': 100,
            'safety': 500,
            'holes': {
                'x_start': 100.,
                'x_dist': 200.,
                'y_start': 100.,
                'y_dist': 200.,
                'diameter': 13.
            }
            }

    parts = climbing_wall(**wall)

    display, start_display, add_menu, add_function_to_menu = init_display()
    for part in parts:
        display.DisplayShape(part._shape, update=False)
    display.FitAll()
    start_display()

    #TO DO
    # draw annotated bounding box
    # pretty print needed material (e.g. 2x plywood 1200x1000x21, 8x bars 2000x ... )
    # add GUI with pyqt
    # export to step, stl
