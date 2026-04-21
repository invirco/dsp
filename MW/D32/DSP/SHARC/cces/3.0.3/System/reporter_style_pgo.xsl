<?xml version="1.0" encoding="utf-8"?>
<!-- *********************************************************************** -->
<!-- reporter_style_pgo.xsl                                                  -->
<!-- Copyright 2008-2020 Analog Devices, Inc.  All rights reserved.          -->
<!-- *********************************************************************** -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html"/>
  <!-- code coverage -->
  <xsl:template match="pgo_out">
    <h2>Code Coverage Report</h2>
    <table border="0" width="90%" cellspacing="0">
      <tr><b>Summary:</b></tr>
      <tr>
        <table border="0" width="100%" cellspacing="0">
          <tr><td width="50%">
            <div class="pgo_percent_outer">
              <xsl:element name="div">
                <xsl:if test="@line_coverage != ''">
                  <xsl:attribute name="style">width:<xsl:value-of select="@line_coverage"/>%; </xsl:attribute>
                  <xsl:attribute name="class">pgo_percent_inner</xsl:attribute>
                  <xsl:value-of select="@line_coverage"/>% lines 
                </xsl:if>
              </xsl:element>
            </div>
            <div>
              <xsl:value-of select="@lines_hit"/> of <xsl:value-of select="@total_lines"/> lines hit.
            </div>
          </td><td width="50%">
            <div class="pgo_percent_outer">
              <xsl:element name="div">
                <xsl:if test="@block_coverage != ''">
                  <xsl:attribute name="style">width:<xsl:value-of select="@block_coverage"/>%; </xsl:attribute>
                  <xsl:attribute name="class">pgo_percent_inner</xsl:attribute>
                  <xsl:value-of select="@block_coverage"/>% basic blocks
                </xsl:if>
              </xsl:element>
            </div>
            <div>
              <xsl:value-of select="@blocks_hit"/> of <xsl:value-of select="@total_blocks"/> basic blocks hit.
            </div>
          </td></tr>
        </table>
      </tr>
      <tr valign="top">
        <td align="left">
          <b>These statistics have been generated from:</b>
          <xsl:text disable-output-escaping="yes"> </xsl:text>
          <xsl:value-of select="@input_filename"/>
        </td>
      </tr>
      <xsl:if test="@percent_lines_missed &gt; 1.0">
      <tr valign="top">
        <td align="left">
          <br/>
          <table border="0" width="100%" cellspacing="0" bgcolor="#ffffff">
            <tr>
              <td>
                <xsl:element name="a">
                  <xsl:attribute name="id">im_note_<xsl:value-of select='@xsl_note_pos_style'/></xsl:attribute>
                  <xsl:attribute name="href">javascript:showHideElement(&quot;note_<xsl:value-of select='@xsl_note_pos_style'/>&quot;, false);
                  </xsl:attribute>
                  <xsl:attribute name="style">text-decoration: none;</xsl:attribute>
                  <xsl:text>-</xsl:text>
                </xsl:element>                
              </td>
              <td>
                <b>Warning:</b> failed to record <b><xsl:value-of select="@percent_lines_missed"/>%</b> of data during the execution of the application.
              </td>
            </tr>
            <xsl:element name="tr">
                <xsl:attribute name="style">display:table-row</xsl:attribute>
                <xsl:attribute name="id">sp_note_<xsl:value-of select='@xsl_note_pos_style'/></xsl:attribute>              
              <td colspan="2">
                <table border="1" width="100%" cellspacing="0" bgcolor="#ffffff">
                  <tr>
                    <td>
                      The above warning occurs when an internal PGO H/W buffer overflows.<br/>
                      When the buffer overflows, for a multi-threaded or multi-core application, PGO data can be missed.<br/>
                      There are two ways that you can avoid the buffer overflowing:
                      <ol>
                        <li>
                          Reduce the percentage of the PGO H/W buffer that is used, before it is flushed to the host PC.<br/>
                          This can be achieved using PGO H/W functions: <i>pgo_hw_get_flush_limit</i> and <i>pgo_hw_set_flush_limit</i>.<br/>
                          These functions are declared in the header file <i>pgo_hw_public.h</i>.<br/>
                          The function, <i>pgo_hw_set_flush_limit</i>, takes an unsigned value from 0 to 100, representing the percentage
                          of the buffer that is used before it is flushed.<br/>
                          By default the percentage is set to 75.
                        </li>
                        <li>
                          Extend the PGO H/W data memory segment in the Linker Description File (LDF).<br/>
                          A larger buffer will result in less frequent flushing of PGO H/W data, and may avoid the problem.
                        </li>
                      </ol>
                      Method 1 is recommended for resolving this issue.<br/><br/>
                      This warning means that the analysis of your application may be incorrect and incomplete, and passing
                      the PGO output data file back into the Compiler, to perform further optimisations, may yield unexpected
                      results.
                    </td>
                  </tr>
                </table>
              </td>
            </xsl:element>
          </table>
        </td>
      </tr>
      </xsl:if>
      <tr>
        <td>
          <xsl:for-each select="pgo_file">
            <p/>
            <table border="0" width="100%" cellspacing="0" bgcolor="#ffffff">
              <tr>
                <td colspan="2">
                  <table width="100%">
                    <tr>
                      <td width="10px">
                        <xsl:element name="a">
                          <xsl:attribute name="id">im_pgo_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                          <xsl:attribute name="href">javascript:showHideElement(&quot;pgo_<xsl:value-of select='@xsl_pos_style'/>&quot;, true);</xsl:attribute>
                          <xsl:attribute name="style">text-decoration: none;</xsl:attribute>
                          <xsl:text>+</xsl:text>
                        </xsl:element>
                      </td>
                      <td align="left">
                        <b><xsl:value-of select="@filename"/></b>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td width="50%">
                  <div class="pgo_percent_outer">
                    <xsl:element name="div">
                      <xsl:if test="@line_coverage != ''">
                        <xsl:attribute name="style">width:<xsl:value-of select="@line_coverage"/>%; </xsl:attribute>
                        <xsl:attribute name="class">pgo_percent_inner</xsl:attribute>
                        <xsl:value-of select="@line_coverage"/>% lines 
                      </xsl:if>
                    </xsl:element>
                  </div>
                </td><td width="50%">
                  <div class="pgo_percent_outer">
                    <xsl:element name="div">
                      <xsl:if test="@block_coverage != ''">
                        <xsl:attribute name="style">width:<xsl:value-of select="@block_coverage"/>%; </xsl:attribute>
                        <xsl:attribute name="class">pgo_percent_inner</xsl:attribute>
                        <xsl:value-of select="@block_coverage"/>% basic blocks
                      </xsl:if>
                    </xsl:element>
                  </div>
                </td>
              </tr>
            </table>
            <table border="1" width="99%" align="right" cellspacing="0" style="background-color: #b0c4de; display:none;">
              <xsl:attribute name="id">sp_pgo_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
              <xsl:choose>
                <xsl:when test="pgo_function">
                  <xsl:for-each select="pgo_function">
                    <tr>
                      <td valign="top" colspan="2">
                        <table width="100%">
                          <tr>
                            <td width="10px">
                              <xsl:element name="a">
                                <xsl:attribute name="id">im_pgo_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                                <xsl:attribute name="href">javascript:showHideElement(&quot;pgo_<xsl:value-of select='@xsl_pos_style'/>&quot;, false);</xsl:attribute>
                                <xsl:attribute name="style">text-decoration: none;</xsl:attribute>
                                <xsl:text>+</xsl:text>
                              </xsl:element>
                            </td>
                            <td>
                              <b><xsl:value-of select="@func_name"/></b>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                    <tr> 
                      <td valign="top">
                        <table border="0" width="100%" cellspacing="0">
                        <tr><td width="50%">
                          <div class="pgo_percent_outer">
                            <xsl:element name="div">
                              <xsl:if test="@line_coverage != ''">
                                <xsl:attribute name="style">width:<xsl:value-of select="@line_coverage"/>%;</xsl:attribute>
                                  <xsl:attribute name="class">pgo_percent_inner</xsl:attribute>
                                <xsl:value-of select="@line_coverage"/>% lines 
                              </xsl:if>
                           </xsl:element>
                        </div>
                      </td><td width="50%">
                        <div class="pgo_percent_outer">
                          <xsl:element name="div">
                            <xsl:if test="@block_coverage != ''">
                              <xsl:attribute name="style">width:<xsl:value-of select="@block_coverage"/>%;</xsl:attribute>
                              <xsl:attribute name="class">pgo_percent_inner</xsl:attribute>
                              <xsl:value-of select="@block_coverage"/>% basic blocks
                            </xsl:if>
                          </xsl:element>
                        </div>
                        </td>
                        </tr>
                        </table>
                      </td>
                    </tr>
                    <xsl:element name="tr">
                    <xsl:attribute name="style">display:none; background-color: #ffffff;</xsl:attribute>
                    <xsl:attribute name="id">sp_pgo_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                      <td colspan="2">
                        <table border="0" width="100%" cellspacing="0">
                          <tr>                            
                            <td>
                              <table border="0" width="100%" cellspacing="0">
                                <thead>
                                  <td width="20%"><b>Line Number</b></td>
                                  <td width="20%"><b>Line Coverage</b></td>                          
                                  <td align="60%"><b>Function definition</b></td>
                                </thead>
                                <xsl:for-each select="pgo_line">
                                  <tr>
                                    <td align="center" width="20%">
                                      <xsl:value-of select='@found_at_line'/>
                                    </td>
                                    <td align="center" width="20%">
                                      <xsl:choose>
                                        <xsl:when test="@in_block != 0">
                                          <xsl:choose>
                                            <xsl:when test="@hit = 0">
                                              <div style="color:#ff0000;"><xsl:value-of select='@hit'/></div>
                                            </xsl:when>
                                            <xsl:otherwise>
                                              <xsl:value-of select='@hit'/>
                                            </xsl:otherwise>
                                          </xsl:choose>
                                        </xsl:when>
                                      </xsl:choose>
                                    </td>
                                    <xsl:choose>
                                      <xsl:when test="@in_block = 0">
                                        <td align="left" class="func_def_no_block">
											                    <xsl:value-of select='.' disable-output-escaping="yes"/>
                                        </td>
                                      </xsl:when>
                                      <xsl:when test="@hit = 0">
                                        <td align="left" class="func_def_miss">
											                    <xsl:value-of select='.' disable-output-escaping="yes"/>
                                        </td>
                                      </xsl:when>
                                      <xsl:otherwise>
                                        <td align="left" class="func_def_hit">
											                    <xsl:value-of select='.' disable-output-escaping="yes"/>
                                        </td>
                                      </xsl:otherwise>
                                    </xsl:choose>
                                  </tr>
                                </xsl:for-each>
                              </table>
                            </td>
                          </tr>
                        </table>
                      </td>                      
                    </xsl:element>
                  </xsl:for-each>
                </xsl:when>
                <xsl:otherwise>
                  <tr>
                    <td colspan="3" align="center" bgcolor="#ffffff">
                      <b>No Code Coverage Information Available.</b>
                      <xsl:if test="@exists = &quot;no&quot;">
                        <br/><b><font color="red">The file does not exist at its specified location.</font></b>
                      </xsl:if>
                    </td>
                  </tr>
                </xsl:otherwise>
              </xsl:choose>
            </table>
            <p/>
          </xsl:for-each>
        </td>        
      </tr>      
      <tr>
        <td colspan="2" align="left"><p><b>Key:</b></p></td>
      </tr><tr>
        <table border="1px solid">
          <tr>
            <td>
              <div class="func_def_hit">line that has been executed.</div>
              <div class="func_def_miss">line that has not been executed.</div>
              <div class="func_def_no_block">line that has no associated code.</div>
            </td>
          </tr>
        </table>
      </tr>

    </table>
    <xsl:if test="@percent_lines_missed &gt; 1.0">
      <xsl:element name="script">
        javascript:showHideElement(&quot;note_<xsl:value-of select='@xsl_note_pos_style'/>&quot;, false);
      </xsl:element>
    </xsl:if>
  </xsl:template>
</xsl:stylesheet>
