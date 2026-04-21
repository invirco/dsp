<?xml version="1.0" encoding="utf-8"?>
<!-- *********************************************************************** -->
<!-- reporter_style_instrprof.xsl                                            -->
<!-- Copyright 2008-2010 Analog Devices, Inc.  All rights reserved.          -->
<!-- *********************************************************************** -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html"/>
  <!-- instrumented profiling -->
  <xsl:template match="mon_out">
    <h2>Instrumented Profiling Report</h2>
    <table border="0" width="90%" cellspacing="0">
      <!-- The total amount in cycles the program took. -->
      <xsl:variable name="total">
        <xsl:value-of select="sum(mon_func/mon_exec/@func_only)"/>
      </xsl:variable>
      <tr>
        <td align="left" colspan="3">
          <b>These statistics have been generated from:</b>
          <xsl:text> </xsl:text><xsl:value-of select="@input_filename"/>
        </td>
      </tr>
      <tr>
        <td colspan="2" height="20"></td>
      </tr>
      <tr>
        <td align="left" width="35%">
          <b>Function's name</b>
        </td>
        <td align="left" width="25%">
          <b>Filename</b>
        </td>
        <td align="center" width="40%">
          <b>Percentage of time spent executing this function<br/>(0% - 100%)</b>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          <table border="1" width="100%" cellspacing="0">
            <tr style="background-color: #b0c4de;">
              <td align="left" style="font-weight: bold;">
                <div style="float: left; text-align: left; padding: 5px;">
                  <xsl:element name="a">
                    <xsl:attribute name="href">javascript:showHideElement(&quot;MyHeader&quot;, true);</xsl:attribute>
                    <xsl:attribute name="style">text-decoration: none;</xsl:attribute>
                    <xsl:attribute name="id">im_MyHeader</xsl:attribute>
                    <xsl:text>-</xsl:text>
                  </xsl:element>
                </div>
                <xsl:element name="div">
                  <xsl:attribute name="style">float: left; text-align: left; padding: 5px;</xsl:attribute>
                  <xsl:attribute name="title">Overall program summary</xsl:attribute>Overall program summary
                </xsl:element>
              </td>
            </tr>
            <tr>
              <td>
                <table cellspacing="0" cellpadding="0" style="display:table" border="0" width="100%" id="sp_MyHeader">
                  <tr>
                    <td>
                      <xsl:for-each select="mon_func">
                        <xsl:call-template name="my_mon_func">
                          <xsl:with-param name="calc_total"><xsl:value-of select="$total"/></xsl:with-param>
                          <xsl:with-param name="my_install"><xsl:value-of select="../../@install_path"/></xsl:with-param>
                        </xsl:call-template>
                      </xsl:for-each>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr><td><br/></td></tr>
      <tr>
        <td colspan="3">
          <xsl:for-each select="mon_thread">
            <table border="1" width="100%" cellspacing="0">
              <tr style="background-color: #b0c4de;">
                <td align="left" style="font-weight: bold;">
                  <div style="float: left; text-align: left; padding: 5px;">
                    <xsl:element name="a">
                      <xsl:attribute name="href">javascript:showHideElement(&quot;prf_<xsl:value-of select="@thread_uid"/>&quot;, true);</xsl:attribute>
                      <xsl:attribute name="style">text-decoration: none;</xsl:attribute>
                      <xsl:attribute name="id">im_prf_<xsl:value-of select="@thread_uid"/></xsl:attribute>
                      <xsl:text>-</xsl:text>
                    </xsl:element>
                  </div>
                  <xsl:element name="div">
                    <xsl:attribute name="style">float: left; text-align: left; padding: 5px;</xsl:attribute>
                    <xsl:attribute name="title"><xsl:value-of select="@thread_name"/></xsl:attribute>
                    Thread Name: <xsl:value-of select="@thread_name"/>
                  </xsl:element>                  
                </td>
              </tr>
              <tr>
                <td>                  
                  <xsl:element name="table">
                  <xsl:attribute name="cellspacing">0</xsl:attribute>
                  <xsl:attribute name="cellpadding">0</xsl:attribute>
                  <xsl:attribute name="border">0</xsl:attribute>
                  <xsl:attribute name="width">100%</xsl:attribute>
                  <xsl:attribute name="style">display:table;</xsl:attribute>
                  <xsl:attribute name="id">sp_prf_<xsl:value-of select="@thread_uid"/></xsl:attribute>
                    <tr>
                      <td>
                        <!-- The total amount in cycles the program took. -->
                        <xsl:variable name="thread_total"><xsl:value-of select="sum(mon_func/mon_exec/@func_only)"/></xsl:variable>
                        <xsl:for-each select="mon_func">
                          <xsl:call-template name="my_mon_func">
                            <xsl:with-param name="calc_total"><xsl:value-of select="$thread_total"/></xsl:with-param>
                            <xsl:with-param name="my_install"><xsl:value-of select="../../../@install_path"/></xsl:with-param>
                          </xsl:call-template>
                        </xsl:for-each>
                      </td>
                    </tr>
                  </xsl:element>
                </td>
              </tr>
            </table>
            <br/>
          </xsl:for-each>
        </td>
      </tr>
    </table>
  </xsl:template>

  <xsl:template name="my_mon_func" match="mon_func">
    <xsl:param name="calc_total"/>
    <xsl:param name="my_install"/>
    <table border="0" width="100%" cellspacing="0">
      <tr>
        <td colspan="3" class="call-stack">
          <div style="float: left; text-align: left; padding: 5px;">
            <xsl:element name="a">
              <xsl:attribute name="href">javascript:showHideElement(&quot;prf_<xsl:value-of select='mon_exec/@xsl_pos_style'/>&quot;, true);</xsl:attribute>
              <xsl:attribute name="style">text-decoration: none;</xsl:attribute>              
              <xsl:attribute name="id">im_prf_<xsl:value-of select='mon_exec/@xsl_pos_style'/></xsl:attribute>
              <xsl:text>-</xsl:text>
            </xsl:element>
          </div>
          <xsl:element name="div">
            <xsl:attribute name="style">float: left; text-align: left; font-size: small; padding: 5px;</xsl:attribute>
            <xsl:attribute name="title"><xsl:value-of select="@func_name"/></xsl:attribute>
            <xsl:value-of select="@func_name"/>
          </xsl:element>
        </td>
      </tr>
      <tr>
        <td></td>
        <td width="25%" class="call-stack">
          <xsl:choose>
            <!-- if ! source file then print address -->
            <xsl:when test="@src_file_name">
              <xsl:value-of select="@src_file_name"/>
            </xsl:when>
            <xsl:otherwise>
              <xsl:value-of select="@address"/>
            </xsl:otherwise>
          </xsl:choose>
        </td>
        <xsl:variable name="func_total">
          <xsl:value-of select="mon_exec/@func_only"/>
        </xsl:variable>
        <td width="40%">
        <xsl:variable name="percent">
          <xsl:value-of select="(($func_total div $calc_total) * 100)"/>
        </xsl:variable>
        <div class="overlay">
          <b><xsl:value-of select='format-number($percent, "#0.00")'/>&#37;</b>
        </div>
        <table cellspacing="0" border="1" width="100%">
          <tr>
            <td>
              <xsl:element name="table">
                <xsl:attribute name="cellspacing">0</xsl:attribute>
                <xsl:attribute name="bgcolor">#bcbcbc</xsl:attribute>
                <xsl:attribute name="border">0</xsl:attribute>
                <xsl:attribute name="width">
                  <xsl:value-of select='format-number($percent, "#0.00")'/>%
                </xsl:attribute>
                <tr>
                  <td height='18'></td>
                </tr>
              </xsl:element>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    </table>
    <xsl:element name="table">
      <xsl:attribute name="cellspacing">0</xsl:attribute>
      <xsl:attribute name="style">display:table</xsl:attribute>
      <xsl:attribute name="border">0</xsl:attribute>
      <xsl:attribute name="width">100%</xsl:attribute>
      <xsl:attribute name="id">sp_prf_<xsl:value-of select='mon_exec/@xsl_pos_style'/>
      </xsl:attribute>
      <tr>
        <td width="35%"></td>
        <td width="25%"></td>
        <td>
          <ul>
            <li>Number of times this function was called: <b><xsl:value-of select='mon_exec/@count'/></b></li>
            <li>Number of cycles without calls: <b><xsl:value-of select='mon_exec/@func_only'/></b></li>
            <li>Number of cycles with calls: <b><xsl:value-of select='mon_exec/@func_nested'/></b></li>
          </ul>
        </td>
      </tr>
    </xsl:element>
  </xsl:template>
</xsl:stylesheet>
