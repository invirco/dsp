<?xml version="1.0" encoding="utf-8"?>
<!-- *********************************************************************** -->
<!-- reporter_style_heap.xsl                                                 -->
<!-- Copyright 2008-2013 Analog Devices, Inc. All rights reserved.           -->
<!-- *********************************************************************** -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html"/>
  <!-- Heap debugging library report -->
  <xsl:template match="heap_out">
    <h2>Heap Debugging Report</h2>
    <table border="0" width="90%" cellspacing="0">
      <tr valign="top">
        <td align="left">
          <b>This report was generated from:</b>
          <xsl:text disable-output-escaping="yes"> </xsl:text>
          <xsl:value-of select="@input_filename"/>
          <xsl:choose>
            <xsl:when test="@core_id">
              <xsl:text disable-output-escaping="yes"> </xsl:text>
              <b>for Core <xsl:value-of select="@core_id"/></b>
              </xsl:when>
          </xsl:choose>          
        </td>
      </tr>
    </table>
    <xsl:if test="count(heap) &gt; 1">
      <p align="left"><b>Summary:</b> 
        <table border="1" width="90%" cellspacing="0" style="background-color: #b0c4de;">
          <xsl:for-each select="heap">
            <tr>
              <td style="text-align:center;" width="20%">
                <xsl:element name="a">
                  <xsl:attribute name="href">#heap_<xsl:value-of select='@id'/></xsl:attribute>
                  <b>Heap ID: 
                  <xsl:choose>
                    <xsl:when test="@properly_setup = 1">
                      <xsl:value-of select="@id"/>
                    </xsl:when>
                    <xsl:otherwise>
                      <xsl:value-of select="@id"/> (not created)
                    </xsl:otherwise>
                  </xsl:choose>
                  </b>
                </xsl:element>
              </td>
              <td style="text-align:center;" width="20%"><b>Problems found: 
                <xsl:choose>
                  <xsl:when test="@num_problems &gt; 0">
                    <font color="#CC0000"><xsl:value-of select="@num_problems"/></font>
                  </xsl:when>
                  <xsl:otherwise>
                    <xsl:value-of select="@num_problems"/>
                  </xsl:otherwise>
                </xsl:choose>                
                </b></td>
              <td style="text-align:center;" width="30%"><b>Size: <xsl:value-of select="@size"/> addressable units</b></td>
              <td style="text-align:center;" width="30%"><b>Peak usage: <xsl:value-of select="@peak_usage"/> addressable units</b></td>
            </tr>
          </xsl:for-each>
        </table>
      </p>
    </xsl:if>
    <xsl:if test="@heap_data_missed &gt; 0">
      <table border="0" width="90%" cellspacing="0">
        <tr valign="top">
          <td align="left">
            <br/>
            <table border="0" width="100%" cellspacing="0" bgcolor="#ffffff">
              <tr>
                <td>
                  <xsl:element name="a">
                    <xsl:attribute name="id">im_heap_note_<xsl:value-of select='@xsl_heap_note_pos_style'/></xsl:attribute>
                    <xsl:attribute name="href">
                      javascript:showHideElement(&quot;heap_note_<xsl:value-of select='@xsl_heap_note_pos_style'/>&quot;, false);
                    </xsl:attribute>
                    <xsl:attribute name="style">text-decoration: none;</xsl:attribute>
                    <xsl:text>-</xsl:text>
                  </xsl:element>
                </td>
                <td>
                  <font style="color: #ff0000;">
                    <b>Warning:</b> failed to record <b>
                      <xsl:value-of select="@heap_data_missed"/> addressable units
                    </b> of data during the execution of the application.
                  </font>
                </td>
              </tr>
              <xsl:element name="tr">
                <xsl:attribute name="style">display:table-row</xsl:attribute>
                <xsl:attribute name="id">sp_heap_note_<xsl:value-of select='@xsl_heap_note_pos_style'/></xsl:attribute>
                <td colspan="2">
                  <table border="1" width="100%" cellspacing="0" bgcolor="#ffffff">
                    <tr>
                      <td>
                        The above warning occurs when an internal heap debugging buffer overflows.<br/>
                        When the buffer overflows, for a multi-threaded or multi-core application, heap debugging data can be missed.<p/>
                        You can avoid the buffer overflowing by increasing the heap debugging buffer that is used.<p/>
                        This can be achieved using heap debugging function <i>adi_heap_debug_set_buffer</i>.<br/>
                        This function is declared in the header file <i>heap_debug.h</i>.<p/>
                        The function, <i>adi_heap_debug_set_buffer</i>, takes the start address of the buffer and the size of the buffer in addressable units.<br/>
                        Please refer to the documentation for more information.<p/>
                        This warning means that the analysis of your application may be incorrect and incomplete.
                      </td>
                    </tr>
                  </table>
                </td>
              </xsl:element>
            </table>
          </td>
        </tr>
      </table>
    </xsl:if>
    <xsl:for-each select="heap">
      <h2>Heap <xsl:value-of select='@id'/></h2>
      <table border="0" width="90%" cellspacing="0">
        <tr>
          <td>
            <xsl:element name="a">
              <xsl:attribute name="id">heap_<xsl:value-of select='@id'/></xsl:attribute>
            </xsl:element>
            <table border="1" width="100%" cellspacing="0" style="background-color: #b0c4de;">
              <tr>
                <td width="15%"><b>Heap ID: 
                  <xsl:choose>
                    <xsl:when test="@properly_setup = 1">
                      <xsl:value-of select="@id"/>
                    </xsl:when>
                    <xsl:otherwise>
                      <xsl:value-of select="@id"/> (not created)
                    </xsl:otherwise>
                  </xsl:choose>                
                </b></td>
                <td style="text-align:center;" width="15%"><b>Size: <xsl:value-of select="@size"/><br/>addressable units</b></td>
                <td style="text-align:center;" width="15%"><b>Peak usage: <xsl:value-of select="@peak_usage"/><br/>addressable units</b></td>
                <td style="text-align:center;" width="20%"><b>Available at end: <xsl:value-of select="@size_left"/><br/>addressable units</b></td>
                <td style="text-align:center;" width="20%"><b>Number of problems found: 
                  <xsl:choose>
                    <xsl:when test="@num_problems &gt; 0">
                      <font color="#CC0000"><xsl:value-of select="@num_problems"/></font>
                    </xsl:when>
                    <xsl:otherwise>
                      <xsl:value-of select="@num_problems"/>
                    </xsl:otherwise>
                  </xsl:choose>                
                </b></td>
              </tr>
            </table>
            <xsl:if test="@num_problems &gt; 0">
              <p/>
              <b>Index of potential issues:</b>
              <table border="1" width="100%" cellspacing="0" style="background-color: #b0c4de;">
                <tr>
                  <th width="34%">Problem</th>
                  <th width="33%">Heap Address</th>
                  <th width="33%">Allocation Type</th>
                </tr>
                <xsl:for-each select="heap_address">
                  <xsl:if test="@memory_check != 'Success'">
                    <tr bgcolor="#bcbcbc">
                      <td width="34%" align="center">
                        <xsl:element name="a">
                          <xsl:attribute name="id">im_hpl_idx_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                          <xsl:attribute name="href">#im_hpl_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                          <xsl:choose>
                            <xsl:when test="@memory_check = 'Corrupt'">
                              Heap corruption
                            </xsl:when>
                            <xsl:otherwise>
                              <xsl:value-of select="heap_operation/@op_state"/>
                            </xsl:otherwise>
                          </xsl:choose>
                        </xsl:element>
                      </td>
                      <td width="33%" align="center">
                        <xsl:value-of select="@memory"/>
                      </td>
                      <td width="33%" align="center">
                        <xsl:value-of select="heap_operation/@op_type"/>
                      </td>
                    </tr>
                  </xsl:if>
                </xsl:for-each>
              </table>
            </xsl:if>
            <p/>
            <xsl:choose>
              <xsl:when test="@num_allocations &gt; 0">
                <table border="1" width="100%" cellspacing="0">
                  <thead style="background-color: #b0c4de;">
                    <tr>
                      <th colspan="2">Allocation outcome</th>
                      <th></th>
                    </tr>
                  </thead>
                  <xsl:element name="tbody">
				            <xsl:attribute name="id">hpl_<xsl:value-of select='heap_address/@xsl_pos_style'/></xsl:attribute>
                    <xsl:for-each select="heap_address">
                      <xsl:if test="count(heap_operation)">
                        <xsl:element name="tr">
                          <xsl:choose>
                            <xsl:when test="heap_operation/@op_type = &quot;initialization&quot;">
                              <xsl:attribute name="style">background-color: #8b475d;</xsl:attribute>
                            </xsl:when>
                            <xsl:when test="@memory_check = 'Success'">
                              <xsl:attribute name="style">background-color: #bcbcbc;</xsl:attribute>
                            </xsl:when>
                            <xsl:otherwise>
                              <xsl:attribute name="style">background-color: #ff3333;</xsl:attribute>
                            </xsl:otherwise>
                          </xsl:choose>
                          <td width="25px">
                            <center>
                              <div style="float: left; text-align: left; padding: 5px;">
                                <xsl:element name="a">
                                  <xsl:attribute name="id">im_hpl_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                                  <xsl:attribute name="href">javascript:showHideElement(&quot;hpl_<xsl:value-of select='@xsl_pos_style'/>&quot;, false);</xsl:attribute>
                                  <xsl:attribute name="style">text-decoration: none;</xsl:attribute>                          
                                  <xsl:text>-</xsl:text>
                                </xsl:element>
                              </div>
                            </center>
                          </td>
                          <xsl:choose>
                            <xsl:when test="@memory_check = 'Success'">
                            <td width="10%">
                              <xsl:value-of select="@memory_check"/> 
                            </td>
                            </xsl:when>
                            <xsl:otherwise>
                            <td width="10%" style="font-weight: bold;">
                              <xsl:value-of select="@memory_check"/>                                                     
                            </td>
                            </xsl:otherwise>
                          </xsl:choose>
                          <xsl:choose>
                            <xsl:when test="heap_operation/@op_type = &quot;initialization&quot;">
                              <td style="text-align: center;">
                                (The heap has been re-initialized, the free list emptied, and all records within the heap discarded)
                              </td>
                            </xsl:when>
                            <xsl:otherwise>                                      
                              <td style="text-align: center;">					                			                
                                <xsl:if test="@memory_check = &quot;Corrupt&quot;">
                                  <div style="text-align: center; padding: 5px; font-weight: normal;">
                                    Memory corrupted at address <b><xsl:value-of select="@corruption_address"/></b>
                                    with value <b><xsl:value-of select="@corruption_value"/></b>
                                  </div>
                                </xsl:if>
                                <b><xsl:value-of select="@memory"/></b>
                                <xsl:choose>
						                      <xsl:when test="(heap_operation/@op_type = &quot;free&quot;) 
							  		                  or (heap_operation/@op_type = &quot;realloc_free&quot;)
								  	                  or (heap_operation/@op_type = &quot;delete&quot;)
									                    or (heap_operation/@op_type = &quot;delete array&quot;)">
							                      (memory location passed to deallocation routine)
						                      </xsl:when>
  						                    <xsl:otherwise>
	  						                    (memory location returned by allocation routine)
		  				                    </xsl:otherwise>
			  	  	                  </xsl:choose>                          
                              </td>
                            </xsl:otherwise>
                          </xsl:choose>
                        </xsl:element>
                        <xsl:element name="tr">
                          <xsl:attribute name="style">display:table-row;</xsl:attribute>
                          <xsl:attribute name="id">sp_hpl_<xsl:value-of select='@xsl_pos_style'/></xsl:attribute>
                          <td colspan="2"></td>
                          <td>
                            <table border="0" width="100%" cellspacing="0">
                              <thead>
                                <tr style="background-color: #b0c4de;">
                                  <th width="20%">Heap operation</th>
                                  <th colspan="2">Called from</th>
                                </tr>
                              </thead>
                              <xsl:for-each select="heap_operation">
							                  <xsl:call-template name="my_heap_operation"/>
                              </xsl:for-each>						
						                  <xsl:if test="count(group_address/group_operation)">						  
						                    <tr>
							                    <td colspan="3">
								                    <center>
									                    <table border="0" width="90%" cellspacing="0">
										                    <tr style="font-weight: bold; text-align: center; background-color: #b0c4de;">
											                    <td width="20%">Associated operation</td>
											                    <td colspan="2">Called from</td>
										                    </tr>
									                    </table>
								                    </center>
							                    </td>
						                    </tr>						  
						                  </xsl:if>
						                  <xsl:for-each select="group_address/group_operation">
						                    <tr>
							                    <td colspan="3" style="align: center;">
								                    <center>
									                    <table border="0" width="90%" cellspacing="0">
										                    <xsl:call-template name="my_heap_operation"/>
									                    </table>
								                    </center>
							                    </td>
						                    </tr>
						                  </xsl:for-each>
                            </table>
                          </td>
                        </xsl:element>
				              </xsl:if>
                    </xsl:for-each>
                  </xsl:element>
                </table>
              </xsl:when>
              <xsl:otherwise>
                <table border="1" width="100%" cellspacing="0">
                  <tr style="background-color: #bcbcbc;">
                    <td colspan="3" style="text-align: center;">
                      No memory allocations or deallocations were performed on Heap <xsl:value-of select="@id"/>.
                    </td>
                  </tr>
                </table>
              </xsl:otherwise>
            </xsl:choose>
            <p/>
          </td>
        </tr>
      </table>
    </xsl:for-each>
    <xsl:if test="@heap_data_missed &gt; 0">
      <xsl:element name="script">
        javascript:showHideElement(&quot;heap_note_<xsl:value-of select='@xsl_heap_note_pos_style'/>&quot;, false);
      </xsl:element>
    </xsl:if>    
    </xsl:template>

	<xsl:template name="my_heap_operation" match="heap_operation | group_operation">
	  <xsl:if test="@op_thread_name">
		<tr>
		  <td align="center" class="call-stack">
			<xsl:text>Thread ID:</xsl:text>
			<b><xsl:value-of select='@op_thread_name'/></b>
		  </td>
		  <td colspan="2"></td>
		</tr>
	  </xsl:if>
	  <tr>
		<td width="20%" valign="top" align="center" class="call-stack">
		  <xsl:element name="div">
			<xsl:attribute name="style">border-width: 0px;</xsl:attribute>
			<xsl:choose>
				<xsl:when test="@op_is_group = 'false'">
					<xsl:attribute name="id">hpl_<xsl:value-of select='@op_connect_id'/></xsl:attribute>
				</xsl:when>
				<xsl:otherwise>
					<xsl:attribute name="id">grp_<xsl:value-of select='@op_connect_id'/></xsl:attribute>
				</xsl:otherwise>
			</xsl:choose>	
			<xsl:choose>
				<xsl:when test="@op_is_group = 'false'">					
					<xsl:element name="a">						
						<xsl:attribute name="href">#grp_<xsl:value-of select='@op_connect_id'/></xsl:attribute>
						<xsl:attribute name="style">text-decoration: none;</xsl:attribute>
						<xsl:attribute name="onMouseOver">javascript:setHighlightHeapConnections(&quot;<xsl:value-of select='@op_connect_id'/>&quot;);</xsl:attribute>
						<xsl:attribute name="onMouseOut">javascript:clrHighlightHeapConnections(&quot;<xsl:value-of select='@op_connect_id'/>&quot;);</xsl:attribute>
						<xsl:value-of select='@op_type'/>
					</xsl:element>					
				</xsl:when>
				<xsl:otherwise>
					<xsl:element name="a">						
						<xsl:attribute name="href">#hpl_<xsl:value-of select='@op_connect_id'/></xsl:attribute>
						<xsl:attribute name="style">text-decoration: none;</xsl:attribute>
						<xsl:attribute name="onMouseOver">javascript:setHighlightHeapConnections(&quot;<xsl:value-of select='@op_connect_id'/>&quot;);</xsl:attribute>
						<xsl:attribute name="onMouseOut">javascript:clrHighlightHeapConnections(&quot;<xsl:value-of select='@op_connect_id'/>&quot;);</xsl:attribute>
						<xsl:value-of select='@op_type'/>
					</xsl:element>
				</xsl:otherwise>					
			</xsl:choose>
          </xsl:element>
		  <xsl:if test="@op_is_group = 'false'">
			<xsl:choose>
			  <xsl:when test="@op_state = 'Ok'">
				<font style="font-size: small; font-weight: bold;">
				  <xsl:value-of select='@op_state'/>
				</font>
			  </xsl:when>
			  <xsl:otherwise>
				<font style="font-size: small; color: #ff0000; font-weight: bold;">
				  <xsl:value-of select='@op_state'/>
				</font>
			  </xsl:otherwise>
			</xsl:choose>
			<br/>
			<font style="font-size: small; font-weight: bold;">Size: <xsl:value-of select='@op_size'/></font>
		  </xsl:if>
		</td>
		<td colspan="2">
		  <table width="100%" cellspacing="0" border="0">
			<tr>
			  <td>
				  <table width="100%" cellspacing="0" border="0">
					<xsl:choose>
					  <xsl:when test="heap_op_call_stack/@func_name">
						<xsl:for-each select="heap_op_call_stack">
						  <xsl:if test="    (@func_name != &quot;start&quot;) 
										and (@func_name != &quot;ctor&quot;)
										and not(contains(@func_name, &quot;__sti&quot;))
										and not(contains(@func_name, &quot;__ctorloop&quot;))
										and not(contains(@func_name, &quot;__process_needed_destruct&quot;))">
							<tr>
							  <td class="call-stack" style="border-bottom: 1px solid #000000; width: 20%; text-align: right;">$PC = <xsl:value-of select='@func_address'/></td>
							  <td style="border-bottom: 1px solid #000000; width: 5%"></td>
							  <td style="border-bottom: 1px solid #000000; text-align: left;">
								<xsl:element name="a">
								  <xsl:attribute name="class">call-stack</xsl:attribute>
								  <xsl:attribute name="title">
									<xsl:value-of select="@func_name"/>
								  </xsl:attribute>
								  <xsl:value-of select='@func_name'/>
								</xsl:element>
							  </td>										  
							</tr>
						  </xsl:if>
						</xsl:for-each>
					  </xsl:when>
					  <xsl:otherwise>
						<tr>
						  <td align="center">
							<b>No call stack available.</b><br/>
							The associated heap operation might have taken place before recording started.
						  </td>
						</tr>
					  </xsl:otherwise>
					</xsl:choose>
				  </table>
				</td>
			</tr>
		  </table>
		</td>
	  </tr>
	</xsl:template>
  </xsl:stylesheet>
  
